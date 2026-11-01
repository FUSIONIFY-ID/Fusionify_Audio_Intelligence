"""Bounded timed transcripts, script alignment and subtitle export."""
import html
import re
import unicodedata
from typing import Annotated
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator
from .rhythm import Number

Time=Annotated[Number,Field(ge=0,le=180)]


def tokens(text):
    return re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',text).casefold(),re.UNICODE)


class Word(BaseModel):
    model_config=ConfigDict(extra='forbid')
    start_s:Time
    end_s:Time
    text:Annotated[StrictStr,Field(min_length=1,max_length=200)]
    probability:Annotated[Number,Field(ge=0,le=1)]|None=None

    @model_validator(mode='after')
    def ordered(self):
        if self.end_s<=self.start_s or not tokens(self.text):raise ValueError('Word requires text and a positive time range.')
        return self


class Segment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    start_s:Time
    end_s:Time
    text:Annotated[StrictStr,Field(min_length=1,max_length=4000)]
    words:Annotated[list[Word],Field(max_length=500)]=Field(default_factory=list)

    @model_validator(mode='after')
    def ordered(self):
        if self.end_s<=self.start_s or not tokens(self.text):raise ValueError('Segment requires text and a positive time range.')
        previous=self.start_s
        for word in self.words:
            if word.start_s<previous or word.end_s>self.end_s:raise ValueError('Words must be ordered, non-overlapping and inside their segment.')
            previous=word.end_s
        if self.words and tokens(' '.join(w.text for w in self.words))!=tokens(self.text):
            raise ValueError('Word text must match its segment text.')
        return self


def validate_segments(segments,duration):
    if not isinstance(segments,list) or len(segments)>500:raise ValueError('At most 500 transcript segments are supported.')
    parsed=[];previous=0.;length=0;word_count=0
    for item in segments:
        segment=Segment.model_validate(item);length+=len(segment.text);word_count+=len(segment.words)
        if segment.start_s<previous or segment.end_s>duration+.00001:
            raise ValueError('Segments must be ordered, non-overlapping and within source duration.')
        previous=segment.end_s;parsed.append(segment.model_dump(exclude_none=True))
    if length>40000 or word_count>5000:raise ValueError('Transcript exceeds 40000 characters or 5000 words.')
    return parsed


def language_code(language):
    if language is not None and (not isinstance(language,str) or not re.fullmatch(r'[a-z]{2,3}',language)):
        raise ValueError('Language must be a two/three-letter lowercase code or null for automatic detection.')
    return language


def page(record,offset=0,limit=50,include_words=False):
    if type(offset)!=int or offset<0 or type(limit)!=int or not 1<=limit<=100 or type(include_words)!=bool:
        raise ValueError('Use nonnegative integer offset, limit 1 to 100, and boolean include_words.')
    segments=record['segments'];end=offset+limit
    return {k:v for k,v in record.items() if k!='segments'} | {
        'segments':[s if include_words else {k:v for k,v in s.items() if k!='words'} for s in segments[offset:end]],
        'segment_count':len(segments),'next_offset':end if end<len(segments) else None}


def review_hypothesis(segments,samples,origin):
    """Navigation flags, never a calibrated probability of correct speech."""
    from .engine import SR
    flags=[];low=0;silent=0;missing=0
    for si,segment in enumerate(segments):
        if not segment.get('words'):missing+=1
        for wi,word in enumerate(segment.get('words',[])):
            reasons=[];p=word.get('probability')
            if p is not None and p<.5:low+=1;reasons.append('model_probability_below_0.5')
            start=max(0,int(word['start_s']*SR));end=min(len(samples),int(np.ceil(word['end_s']*SR)))
            if end>start and not np.any(samples[start:end]):silent+=1;reasons.append('word_span_is_digital_silence')
            if reasons:
                flags.append({'segment_index':si,'word_index':wi,'text':word['text'],
                              'start_s':word['start_s'],'end_s':word['end_s'],'reasons':reasons})
    return {'inference_performed':origin=='local_faster_whisper',
            'digital_silence_gate':origin=='local_signal_gate',
            'low_probability_word_count':low,'digital_silence_word_count':silent,
            'segments_without_word_timings':missing,'flagged_word_count':len(flags),
            'flags':flags[:20],'flags_truncated':len(flags)>20,
            'note':'Flags help listening review. Model probabilities are not calibrated accuracy scores; no flags does not verify words or pronunciation.'}


def check(record,expected_text,max_edits=50):
    if not isinstance(expected_text,str) or not 1<=len(expected_text)<=20000:
        raise ValueError('Expected text must contain 1 to 20000 characters.')
    if type(max_edits)!=int or not 1<=max_edits<=100:raise ValueError('max_edits must be 1 to 100.')
    expected=tokens(expected_text);observed=[];spans=[]
    for segment in record['segments']:
        for part in (segment.get('words') or [segment]):
            units=tokens(part['text']);observed.extend(units)
            spans.extend([{'start_s':part['start_s'],'end_s':part['end_s'],
                           'precision':'word_estimate' if segment.get('words') else 'segment_range'}]*len(units))
    if not expected or len(expected)>1500 or len(observed)>5000:
        raise ValueError('Comparison requires 1–1500 expected tokens and at most 5000 transcript tokens.')
    # Rolling costs and a byte per backtrace cell bound memory below 8 MiB.
    n,m=len(expected),len(observed);trace=np.zeros((n+1,m+1),dtype=np.uint8)
    trace[1:,0]=1;trace[0,1:]=2;previous=list(range(m+1))
    for i,a in enumerate(expected,1):
        row=[i]+[0]*m
        for j,b in enumerate(observed,1):
            costs=(previous[j-1]+(a!=b),previous[j]+1,row[j-1]+1)
            op=min(range(3),key=costs.__getitem__);row[j]=costs[op];trace[i,j]=op
        previous=row
    i,j=n,m;edits=[];counts={'substitutions':0,'omissions':0,'additions':0}
    while i or j:
        op=int(trace[i,j])
        if op==0:
            i-=1;j-=1
            if expected[i]!=observed[j]:
                counts['substitutions']+=1;edits.append({'type':'substitution','expected':expected[i],
                  'observed':observed[j],'expected_token_index':i,'observed_token_index':j,'audio_span':spans[j]})
        elif op==1:
            i-=1;counts['omissions']+=1
            edits.append({'type':'omission','expected':expected[i],'expected_token_index':i,'audio_span':None,
                          'neighbor_audio_span':spans[min(j,m-1)] if m else None})
        else:
            j-=1;counts['additions']+=1
            edits.append({'type':'addition','observed':observed[j],'observed_token_index':j,'audio_span':spans[j]})
    edits.reverse();total=sum(counts.values())
    return {'transcript_id':record['transcript_id'],'origin':record['origin'],
            'comparison_basis':('signal-only digital silence review; no ASR hypothesis' if record['origin']=='local_signal_gate' else
                                'ASR hypothesis' if record['audio_processed'] else 'user-supplied text only; audio not verified'),
            'transcript_review':record.get('review'),
            'expected_token_count':n,'observed_token_count':m,**counts,'edit_count':total,
            'word_error_rate':round(total/n,5),'edits':edits[:max_edits],'edits_truncated':len(edits)>max_edits,
            'normalization':'Unicode NFKC, casefold, punctuation-separated tokens; no inferred homophones or number expansion.',
            'limitations':['Transcript agreement does not prove pronunciation or intonation.',
                           'ASR may mishear words. Inspect flagged spans against original audio.',
                           'Omissions have no detected audio span; neighbor spans are navigation hints only.']}


def subtitle(record,format,start_s=0,end_s=None):
    if format not in ('srt','vtt'):raise ValueError('Subtitle format must be srt or vtt.')
    end_s=record['duration_s'] if end_s is None else end_s
    cues=[];omitted=0;partial=0;crossing_words=0
    for segment in record['segments']:
        a,b=segment['start_s'],segment['end_s']
        if b<=start_s or a>=end_s:continue
        text=segment['text']
        if a<start_s or b>end_s:
            partial+=1
            crossing_words+=sum(w['start_s']<end_s and w['end_s']>start_s and
                                (w['start_s']<start_s or w['end_s']>end_s) for w in segment.get('words',[]))
            words=[w for w in segment.get('words',[]) if w['start_s']>=start_s and w['end_s']<=end_s]
            if not words:omitted+=1;continue
            a,b=words[0]['start_s'],words[-1]['end_s'];text=' '.join(w['text'].strip() for w in words)
        a,b=round((a-start_s)*1000),round((b-start_s)*1000)
        if b<=a:omitted+=1;continue
        # No raw markup, cue delimiters, control characters or injected blank lines.
        text=' '.join(''.join(c if unicodedata.category(c)[0]!='C' else ' ' for c in text).split())
        text=html.escape(text,quote=False).replace('--&gt;','→')
        cues.append((a,b,text))
    def stamp(ms):
        seconds,milli=divmod(ms,1000);minutes,second=divmod(seconds,60);hour,minute=divmod(minutes,60)
        return f'{hour:02}:{minute:02}:{second:02}{"," if format=="srt" else "."}{milli:03}'
    lines=['WEBVTT',''] if format=='vtt' else []
    for i,(a,b,text) in enumerate(cues,1):lines.extend([str(i),f'{stamp(a)} --> {stamp(b)}',text,''])
    return '\n'.join(lines)+'\n',{'cue_count':len(cues),'omitted_partial_or_rounded_segments':omitted,
           'partial_segments_review_required':partial,'words_crossing_trim_omitted':crossing_words,
           'note':'Partial segments require complete in-range word timings; omitted text needs review. Subtitle text is escaped.'}
