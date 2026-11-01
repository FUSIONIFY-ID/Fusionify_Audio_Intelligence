"""Shared real MCP calls, not a provider mock."""
async def exercise_voice(session,aid,payload):
    voice=payload(await session.call_tool('analyze_voice',{'analysis_id':aid}))
    timeline=payload(await session.call_tool('get_voice_timeline',{'voice_id':voice['voice_id'],'limit':2}))
    assert len(timeline['contour'])==2 and timeline['next_offset']==2
    imported=payload(await session.call_tool('import_transcript',{'analysis_id':aid,'language':'id','segments':[
        {'start_s':1,'end_s':2,'text':'Halo dunia','words':[
            {'start_s':1,'end_s':1.4,'text':'Halo'}, {'start_s':1.5,'end_s':2,'text':'dunia'}]}]}))
    tid=imported['transcript_id']
    assert not imported['audio_processed']
    saved=payload(await session.call_tool('get_transcript',{'transcript_id':tid,'include_words':True}))
    assert len(saved['segments'][0]['words'])==2
    check=payload(await session.call_tool('check_spoken_text',{'transcript_id':tid,'expected_text':'Halo semua'}))
    assert check['substitutions']==1 and check['edits'][0]['audio_span']['start_s']==1.5
    assert 'not verified' in check['comparison_basis']
    assert (await session.call_tool('import_transcript',{'analysis_id':aid,'segments':[
        {'start_s':True,'end_s':2,'text':'bad'}]})).isError
    assert (await session.call_tool('transcribe_audio',{'analysis_id':aid,'language':'../bad'})).isError
    project=payload(await session.call_tool('create_video_project',{'analysis_id':aid,'options':{'music_in_s':1,'duration_s':2}}))
    return payload(await session.call_tool('export_transcript',{'transcript_id':tid,'format':'vtt','project_id':project['project_id']}))
