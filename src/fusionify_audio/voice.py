"""Offline periodic-component review. This is not a voice separator or emotion model."""
import math
import numpy as np
from scipy import signal
from .engine import SR


def review(y, declared_source_type='mixed_audio'):
    if declared_source_type not in ('speech','mixed_audio'):
        raise ValueError('Declare source type as speech or mixed_audio.')
    if len(y)<1024 or len(y)>SR*180 or not np.isfinite(y).all():
        raise ValueError('Expected finite decoded audio, 0.05 to 180 seconds.')
    duration=len(y)/SR
    x=signal.resample_poly(y,320,441).astype(np.float64)
    size,hop=1024,320
    x=np.pad(x,(0,max(0,size-len(x))))
    frames=np.lib.stride_tricks.sliding_window_view(x,size)[::hop]
    rms=np.sqrt(np.mean(frames**2,axis=1))
    db=20*np.log10(np.maximum(rms,1e-10))
    gate=max(-55.,float(np.percentile(db,95))-30)
    active=db>gate
    pitches=np.full(len(frames),np.nan);strength=np.zeros(len(frames))
    # Normalized overlap autocorrelation with first strong local peak.
    # Chunking bounds FFT memory for the maximum 180-second input.
    lo,hi=31,269  # include neighbors around the 60–500 Hz search bounds
    for start in range(0,len(frames),256):
        f=frames[start:start+256].copy();f-=f.mean(axis=1,keepdims=True)
        spec=np.fft.rfft(f,n=2048,axis=1)
        corr=np.fft.irfft(spec*spec.conj(),n=2048,axis=1)[:,:hi+1]
        sums=np.concatenate([np.zeros((len(f),1)),np.cumsum(f*f,axis=1)],axis=1)
        lags=np.arange(hi+1)
        denom=np.sqrt(np.maximum(sums[:,size-lags]*(sums[:,size,None]-sums[:,lags]),1e-20))
        ac=corr/denom
        for j,row in enumerate(ac):
            idx=start+j
            if not active[idx]:continue
            peaks,_=signal.find_peaks(row[lo:hi+1])
            candidates=peaks+lo
            candidates=candidates[(candidates>=32)&(candidates<=267)]
            if not len(candidates):continue
            best=float(row[candidates].max())
            strong=candidates[row[candidates]>=max(.8,best*.97)]
            if not len(strong):continue
            lag=int(strong[0]);delta=0.
            if 0<lag<hi:
                a,b,c=row[lag-1:lag+2];den=a-2*b+c
                if abs(den)>1e-12:delta=float(np.clip(.5*(a-c)/den,-.5,.5))
            pitch=16000/(lag+delta)
            if not 59.5<=pitch<=500.5:continue
            pitches[idx]=float(np.clip(pitch,60,500));strength[idx]=min(1.,max(0.,float(row[lag])))
    contour=[]
    for i in range(0,len(frames),5):
        p=pitches[i:i+5];valid=p[np.isfinite(p)]
        contour.append({'time_s':round(min(duration,(i*hop+size/2)/16000),4),
                        'pitch_hz':round(float(np.median(valid)),2) if len(valid)>=min(3,len(p)) else None,
                        'periodicity':round(float(np.median(strength[i:i+5])),3),
                        'rms_dbfs':round(float(np.median(db[i:i+5])),2),
                        'signal_active':bool(active[i:i+5].sum()>=len(p)/2)})
    # Group activity, bridging short gaps; these ranges are not speech detection.
    mask=active.copy()
    changes=np.flatnonzero(np.diff(np.r_[False,~mask,False].astype(int)))
    for a,b in zip(changes[::2],changes[1::2]):
        if a>0 and b<len(mask) and b-a<12:mask[a:b]=True
    def ranges(values):
        edges=np.flatnonzero(np.diff(np.r_[False,values,False].astype(int)))
        return [(max(0,a*hop/16000),min(duration,((b-1)*hop+size)/16000),a,b) for a,b in zip(edges[::2],edges[1::2])]
    phrases=[]
    for a,b,i,j in ranges(mask):
        p=pitches[i:j];valid=p[np.isfinite(p)]
        trend='insufficient_periodic_signal';change=None
        third=max(1,len(p)//3);first=p[:third];last=p[-third:]
        first=first[np.isfinite(first)];last=last[np.isfinite(last)]
        if len(valid)>=max(8,len(p)*.25) and len(first)>=3 and len(last)>=3:
            change=round(float(12*np.log2(np.median(last)/np.median(first))),2)
            trend='rising' if change>1.5 else 'falling' if change< -1.5 else 'level'
        phrases.append({'start_s':round(a,4),'end_s':round(b,4),'pitch_trend':trend,'change_semitones':change,
                        'periodic_frame_fraction':round(float(len(valid)/len(p)),3),
                        'median_rms_dbfs':round(float(np.median(db[i:j])),2),
                        'energy_change_db':round(float(np.median(db[max(i,j-third):j])-np.median(db[i:min(j,i+third)])),2)})
    # Complement the merged ranges so quiet ranges never overlap activity spans.
    quiet=[];cursor=0.
    for a,b,_,_ in ranges(mask):
        if a-cursor>=.25:quiet.append({'start_s':round(cursor,4),'end_s':round(a,4)})
        cursor=b
    if duration-cursor>=.25:quiet.append({'start_s':round(cursor,4),'end_s':round(duration,4)})
    valid=pitches[np.isfinite(pitches)];peak=float(np.abs(y).max())
    summary={'duration_s':round(duration,5),'declared_source_type':declared_source_type,
             'periodic_frame_fraction':round(float(np.isfinite(pitches).mean()),4),
             'pitch_hz_p10_median_p90':[round(float(v),2) for v in np.percentile(valid,[10,50,90])] if len(valid) else None,
             'pitch_range_semitones_p10_p90':round(float(12*np.log2(np.percentile(valid,90)/np.percentile(valid,10))),2) if len(valid) else None,
             'peak_dbfs':round(20*math.log10(max(peak,1e-10)),2),
             'samples_at_or_above_full_scale_fraction':round(float((np.abs(y)>=1).mean()),6),
             'headroom_flag':peak>=.999,'activity_threshold_dbfs':round(gate,2),
             'activity_range_count':len(phrases),'quiet_range_count':len(quiet),
             'time_reference':'seconds from source start',
             'limitations':['Pitch follows a periodic component from 60 to 500 Hz; octave errors are possible.',
                            'Signal activity is not verified speech. Headroom flag does not prove clipping.',
                            'No emotion, identity, pronunciation score or correct-delivery verdict is inferred.']}
    if declared_source_type=='mixed_audio':
        summary['limitations'].insert(0,'Mixed audio: instruments can determine the contour. Do not attribute this to a vocalist.')
    return {'summary':summary,'contour':contour,'activity_ranges':phrases,'quiet_ranges':quiet}
