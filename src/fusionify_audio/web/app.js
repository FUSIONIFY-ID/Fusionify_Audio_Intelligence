'use strict';
const $ = id => document.getElementById(id);
let token = '', assets = [], analysis = null, project = null, projectAnalysis = null;
let savedOptions = '', busy = 0, currentJob = null, currentRenderRevision = null, generation = 0, pollTimer = null;
let rhythmData = null, markers = [], savedMarkers = [], markerHistory = [], taps = [];
let audioJob = null, audioPollTimer = null, reviewGeneration = 0;
const rhythmButtons = ['load-rhythm','listen-original','listen-clicks','add-marker','remove-marker','undo-markers','reset-markers','save-markers','tap-beat','reset-taps','apply-map'];

function error(message) { $('error').textContent = message || ''; $('error').hidden = !message; }
function controls() {
  $('connect').disabled = busy > 0;
  $('audio').disabled = !token || busy > 0 || !!currentJob;
  for (const id of ['choose','save','preview','render']) $(id).disabled = !token || busy > 0 || (['preview','render'].includes(id) && !!currentJob);
  $('cancel').disabled = !currentJob;
  for (const id of rhythmButtons) $(id).disabled = !token || busy > 0 || !!currentJob || (id !== 'load-rhythm' && !rhythmData) || (['listen-original','listen-clicks'].includes(id) && !!audioJob);
  if (token && !busy && !currentJob && rhythmData) {
    $('save-markers').disabled = !markersDirty(); $('undo-markers').disabled = !markerHistory.length;
    $('reset-markers').disabled = !markersDirty(); $('remove-marker').disabled = !markers.length;
  }
}
async function run(fn) {
  error(''); busy++; controls();
  try { return await fn(); } catch (e) { error(e.message || 'The request could not be completed.'); }
  finally { busy--; controls(); }
}
async function call(operation, args = {}) {
  if (!token) throw new Error('Connect to your workspace first.');
  const response = await fetch('/api/call', {method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({operation,arguments:args})});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Workspace request failed.');
  return value;
}
function drawAssets() {
  const selected = $('audio').value;
  const selectedVisuals = new Set([...document.querySelectorAll('[data-visual]:checked')].map(el => el.value));
  $('library').replaceChildren(); $('audio').replaceChildren(new Option('Select audio',''));
  for (const asset of assets) {
    if (asset.kind === 'audio' || asset.kind === 'video') $('audio').add(new Option(asset.filename, asset.asset_id));
    const row = document.createElement('li'), label = document.createElement('label'); label.className = 'asset-label';
    if (asset.kind === 'image' || asset.kind === 'video') {
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = asset.asset_id; checkbox.dataset.visual = 'true'; checkbox.checked = selectedVisuals.has(asset.asset_id); label.append(checkbox);
    }
    const name = document.createElement('span'); name.textContent = asset.filename;
    const kind = document.createElement('span'); kind.className = 'asset-kind'; kind.textContent = asset.kind;
    label.append(name,kind);
    const copy = document.createElement('button'); copy.type = 'button'; copy.className = 'text-button'; copy.textContent = 'Copy ID';
    copy.addEventListener('click', () => run(async () => { await navigator.clipboard.writeText(asset.asset_id); copy.textContent = 'Copied'; setTimeout(() => copy.textContent = 'Copy ID',1500); }));
    row.append(label,copy); $('library').append(row);
  }
  $('library-empty').hidden = assets.length > 0;
  if (assets.some(a => a.asset_id === selected)) $('audio').value = selected;
}
async function refreshAssets() { assets = (await call('list_media_assets',{limit:100})).assets; drawAssets(); }
$('connection').addEventListener('submit', event => { event.preventDefault(); run(async () => {
  if (token) {
    token='';generation++;analysis=null;project=null;projectAnalysis=null;savedOptions='';
    clearRhythm();
    clearTimeout(pollTimer);currentJob=null;assets=[];drawAssets();
    $('video').pause();$('video').removeAttribute('src');$('video').load();$('video').hidden=true;
    $('preview-empty').hidden=false;$('download').hidden=true;$('download').removeAttribute('href');
    $('exports').hidden=true;$('export-link').hidden=true;$('export-link').removeAttribute('href');
    $('analysis').hidden=true;$('progress').value=0;$('upload-status').textContent='';
    $('project-status').textContent='Project not saved yet. No render yet.';
    $('connect').textContent='Connect';$('job-status').textContent='Disconnected';return;
  }
  token = $('token').value.trim(); $('token').value = '';
  if (!token) throw new Error('Enter the workspace token supplied by your server operator.');
  try { await call('get_workspace'); await refreshAssets(); $('connect').textContent = 'Disconnect'; }
  catch (e) { token = ''; throw e; }
}); });
$('choose').addEventListener('click', () => $('files').click());
async function upload(files) {
  if (!token) throw new Error('Connect before uploading files.');
  for (const file of files) {
    if (file.size > 64*1024*1024) throw new Error(`${file.name} exceeds 64 MiB.`);
    $('upload-status').textContent = `Uploading ${file.name}…`;
    const response = await fetch('/api/upload',{method:'POST',headers:{Authorization:`Bearer ${token}`,'X-Filename':encodeURIComponent(file.name),'Content-Type':'application/octet-stream'},body:file});
    const value = await response.json(); if (!response.ok) throw new Error(value.error || 'Upload failed.');
  }
  await refreshAssets(); $('upload-status').textContent = 'Uploaded. Copy an asset ID to use it in Claude; select visual assets to include them in this edit.';
}
$('files').addEventListener('change', () => run(async () => { await upload([...$('files').files]);$('files').value=''; }));
for (const name of ['dragenter','dragover']) $('dropzone').addEventListener(name,e => { e.preventDefault();$('dropzone').classList.add('dragging'); });
for (const name of ['dragleave','drop']) $('dropzone').addEventListener(name,e => { e.preventDefault();$('dropzone').classList.remove('dragging'); });
$('dropzone').addEventListener('drop',e => run(() => upload([...e.dataTransfer.files])));
async function ensureAnalysis() {
  const asset = $('audio').value;
  if (!asset) throw new Error('Select a soundtrack first.');
  if (analysis && analysis.asset === asset) return analysis;
  const version = ++generation;
  $('analysis').hidden = false; $('analysis').textContent = 'Analyzing your actual soundtrack…';
  const report = await call('analyze_audio',{audio_path:asset});
  if (version !== generation || $('audio').value !== asset) throw new Error('Soundtrack changed. Analyze the new selection.');
  analysis = {...report,asset};
  const bpm = report.tempo_bpm_estimate === null ? 'No reliable pulse found' : `~${report.tempo_bpm_estimate.toFixed(2)} BPM`;
  $('analysis').textContent = `${report.duration_s.toFixed(2)} seconds · ${bpm} · ${report.beat_count} candidate beats. Review timing by ear before publishing.`;
  return analysis;
}
$('audio').addEventListener('change', () => {
  if(markersDirty()){$('audio').value=analysis.asset;error('Save your timing copy or reset unsaved markers before changing the soundtrack.');return;}
  analysis=null;generation++;clearRhythm();run(ensureAnalysis);
});
function options() {
  if (!$('project-form').reportValidity()) throw new Error('Check the highlighted project fields.');
  return {title:$('title').value,caption:$('caption').value,style:$('style').value,intensity:$('intensity').value,
    aspect:$('aspect').value,resolution:Number($('resolution').value),music_in_s:Number($('start').value),
    duration_s:$('duration').value === '' ? null : Number($('duration').value),
    asset_ids:[...document.querySelectorAll('[data-visual]:checked')].map(el => el.value)};
}
async function save() {
  if (markersDirty()) throw new Error('Save your timing copy or reset unsaved markers before saving or rendering a project.');
  const audio = await ensureAnalysis(), opts = options(), serialized = JSON.stringify(opts);
  if (project && projectAnalysis === audio.analysis_id) {
    if (serialized !== savedOptions) project = await call('revise_video_project',{project_id:project.project_id,expected_revision:project.revision,changes:opts});
  } else {
    project = await call('create_video_project',{analysis_id:audio.analysis_id,options:opts});projectAnalysis=audio.analysis_id;
  }
  savedOptions = serialized; $('exports').hidden = false;
  $('project-status').textContent = `Saved revision ${project.revision} · ${project.duration_s.toFixed(2)} s · ${project.scene_count} scenes · Project ${project.project_id}`;
  return project;
}
$('save').addEventListener('click', () => run(save));
async function poll() {
  if (!currentJob) return;
  const id = currentJob;
  try {
    const job = await call('get_job_status',{job_id:currentJob});
    if (!token || currentJob !== id) return;
    $('progress').value = job.progress || 0; $('job-status').textContent = `${job.status.charAt(0).toUpperCase()+job.status.slice(1)}${job.status === 'running' ? ` · ${Math.round(100*(job.progress||0))}%` : ''}`;
    if (job.status === 'completed') {
      $('job-status').textContent = `Completed · revision ${currentRenderRevision}`;
      $('preview-empty').hidden = true; $('video').hidden = false; $('video').src = job.download_url;
      $('download').href = job.download_url; $('download').hidden = false;
      currentJob=null;controls();return;
    }
    if (['failed','cancelled','interrupted'].includes(job.status)) { currentJob=null;controls();if(job.error)error(job.error);return; }
    pollTimer = setTimeout(poll,1000);
  } catch (e) { if(currentJob===id){currentJob=null;controls();error(e.message);} }
}
async function render(preview) {
  const saved = await save();
  const job = await call('render_video_project',{project_id:saved.project_id,preview});
  currentJob=job.job_id;currentRenderRevision=saved.revision;$('progress').value=0;$('job-status').textContent=preview?'Queued preview, up to 8 seconds':'Queued full project render';controls();
  await poll();
}
$('preview').addEventListener('click', () => run(() => render(true)));
$('render').addEventListener('click', () => run(() => render(false)));
$('cancel').addEventListener('click', () => run(async () => { if(currentJob)await call('cancel_render_job',{job_id:currentJob}); }));
for (const format of ['json','csv']) $(`export-${format}`).addEventListener('click', () => run(async () => {
  const saved = await save(), result = await call('export_video_timeline',{project_id:saved.project_id,format});
  $('export-link').href=result.download_url;$('export-link').textContent=`Download ${format.toUpperCase()}`;$('export-link').hidden=false;
}));
$('aspect').addEventListener('change', () => { $('viewer').style.aspectRatio=$('aspect').value.replace(':','/'); });

function markersDirty() { return JSON.stringify(markers) !== JSON.stringify(savedMarkers); }
function clearRhythm() {
  reviewGeneration++; clearTimeout(audioPollTimer); audioJob=null; rhythmData=null;
  markers=[]; savedMarkers=[]; markerHistory=[]; taps=[];
  $('review-audio').pause(); $('review-audio').removeAttribute('src'); $('review-audio').load(); $('review-audio').hidden=true;
  $('rhythm-editor').hidden=true; $('markers').replaceChildren();
  $('rhythm-status').textContent='Load a soundtrack to review its timing.';
  $('tap-status').textContent='Play original audio and tap at least four evenly spaced pulses. Applying the grid saves a new analysis.';
}
function drawWaveform() {
  if (!rhythmData) return;
  const canvas=$('waveform'), ctx=canvas.getContext('2d'), w=canvas.width, h=canvas.height;
  const start=Number($('view-start').value), end=Number($('view-end').value), duration=rhythmData.duration_s;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start<0 || end<=start || end>duration) return;
  ctx.clearRect(0,0,w,h);ctx.fillStyle='#536c93';
  rhythmData.waveform.forEach((v,i) => {
    const t=i/rhythmData.waveform.length*duration, x=(t-start)/(end-start)*w;
    if(x<0||x>w)return;
    ctx.fillRect(x,h/2-v[1]*h*.42,Math.max(1,duration/rhythmData.waveform.length/(end-start)*w),Math.max(1,(v[1]-v[0])*h*.42));
  });
  ctx.strokeStyle='#2164f3';ctx.lineWidth=2;ctx.beginPath();
  for(const t of markers) if(t>=start&&t<=end){const x=(t-start)/(end-start)*w;ctx.moveTo(x,12);ctx.lineTo(x,h-12);}ctx.stroke();
  const play=Number($('rhythm-seek').value);ctx.strokeStyle='#c64f15';ctx.lineWidth=3;ctx.beginPath();
  const x=(play-start)/(end-start)*w;ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();
}
function drawMarkers(selected) {
  $('markers').replaceChildren(...markers.map((t,i)=>new Option(`${i+1}. ${t.toFixed(3)} s`,String(i))));
  if(selected!==undefined)$('markers').value=String(selected);
  $('marker-status').textContent=`${markers.length} markers · ${markersDirty()?'Unsaved changes. Save a timing copy before rendering.':rhythmData?.beat_provenance||'No timing loaded.'}`;
  drawWaveform();controls();
}
function editMarkers(next) {
  if(next.length>2000)throw new Error('A timing analysis supports at most 2000 markers.');
  markerHistory.push([...markers]);if(markerHistory.length>50)markerHistory.shift();markers=next;drawMarkers();
}
async function loadRhythm() {
  const audio=await ensureAnalysis(), version=++reviewGeneration;
  clearTimeout(audioPollTimer);audioJob=null;
  $('review-audio').pause();$('review-audio').removeAttribute('src');$('review-audio').load();$('review-audio').hidden=true;
  const data=await call('get_rhythm_review',{analysis_id:audio.analysis_id});
  if(version!==reviewGeneration||analysis?.analysis_id!==audio.analysis_id)return;
  rhythmData=data;markers=data.beats.map(b=>b.time_s);savedMarkers=[...markers];markerHistory=[];
  $('rhythm-editor').hidden=false;$('view-start').value='0';$('view-end').value=String(data.duration_s);
  $('rhythm-seek').max=String(data.duration_s);$('rhythm-seek').value='0';$('marker-time').value='0';$('playhead').value='0.000 s';
  $('map-bpm').value=data.tempo_map.length===1?data.tempo_map[0].bpm:data.tempo_bpm_estimate||'';
  $('map-first').value=markers[0]||0;
  $('rhythm-status').textContent='Waveform ready. Prepare audio, listen and review the markers.';drawMarkers();
}
$('load-rhythm').addEventListener('click',()=>run(async()=>{
  if(markersDirty())throw new Error('Save your timing copy or reset unsaved markers before reloading.');
  await loadRhythm();
}));
for(const id of ['view-start','view-end'])$(id).addEventListener('change',()=>run(async()=>{
  const start=Number($('view-start').value),end=Number($('view-end').value);
  if(!rhythmData||!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end>rhythmData.duration_s)throw new Error('Choose a view range within the soundtrack, with end after start.');
  drawWaveform();
}));
function seek(t) {
  if(!rhythmData)return;
  t=Math.max(0,Math.min(t,rhythmData.duration_s));$('rhythm-seek').value=t;$('marker-time').value=t.toFixed(3);$('playhead').value=`${t.toFixed(3)} s`;
  if($('review-audio').readyState>=1)$('review-audio').currentTime=t;
  drawWaveform();
}
$('waveform').addEventListener('click',e=>{
  const start=Number($('view-start').value),end=Number($('view-end').value),box=$('waveform').getBoundingClientRect();
  if(rhythmData&&start>=0&&end>start&&end<=rhythmData.duration_s)seek(start+(e.clientX-box.left)/box.width*(end-start));
});
$('rhythm-seek').addEventListener('input',()=>seek(Number($('rhythm-seek').value)));
$('review-audio').addEventListener('timeupdate',()=>{
  if(!rhythmData)return;const t=$('review-audio').currentTime;
  $('rhythm-seek').value=t;$('marker-time').value=t.toFixed(3);$('playhead').value=`${t.toFixed(3)} s`;drawWaveform();
});
$('markers').addEventListener('change',()=>seek(markers[Number($('markers').value)]));
$('add-marker').addEventListener('click',()=>run(async()=>{
  const t=Number($('marker-time').value);
  if(!Number.isFinite(t)||t<0||t>=rhythmData.duration_s||$('marker-time').value==='')throw new Error('Marker must be inside the soundtrack.');
  if(markers.some(b=>Math.abs(b-t)<.001))throw new Error('A marker already exists at this position.');
  editMarkers([...markers,t].sort((a,b)=>a-b));drawMarkers(markers.indexOf(t));
}));
$('remove-marker').addEventListener('click',()=>run(async()=>{const i=Number($('markers').value);editMarkers(markers.filter((_,k)=>k!==i));}));
$('undo-markers').addEventListener('click',()=>{if(markerHistory.length){markers=markerHistory.pop();drawMarkers();}});
$('reset-markers').addEventListener('click',()=>{markers=[...savedMarkers];markerHistory=[];drawMarkers();});
async function acceptTiming(result) {
  analysis={...analysis,analysis_id:result.analysis_id,beat_count:result.beat_count};
  project=null;projectAnalysis=null;savedOptions='';$('exports').hidden=true;$('export-link').hidden=true;$('export-link').removeAttribute('href');
  $('video').pause();$('video').removeAttribute('src');$('video').load();$('video').hidden=true;$('preview-empty').hidden=false;
  $('download').hidden=true;$('download').removeAttribute('href');$('progress').value=0;$('job-status').textContent='No render for this timing copy';
  $('analysis').textContent=`${analysis.duration_s.toFixed(2)} seconds · ${result.beat_count} user-directed beats. Original measured BPM remains a separate estimate.`;
  $('project-status').textContent='Timing copy saved. Save a new project to use it. Existing saved projects retain their timing.';
  clearRhythm();await loadRhythm();$('rhythm-status').textContent=`Timing copy saved · ${result.analysis_id}`;
}
$('save-markers').addEventListener('click',()=>run(async()=>{
  const result=await call('correct_beat_markers',{analysis_id:analysis.analysis_id,beat_times_s:markers});await acceptTiming(result);
}));
$('apply-map').addEventListener('click',()=>run(async()=>{
  if(markersDirty())throw new Error('Save your marker edits or reset unsaved markers before replacing them with a tempo map.');
  const bpm=Number($('map-bpm').value),first=Number($('map-first').value),snap=Number($('map-snap').value);
  if(!$('map-bpm').value||!$('map-first').value||!$('map-snap').value)throw new Error('Enter BPM, first beat and snap tolerance.');
  const result=await call('apply_tempo_map',{analysis_id:analysis.analysis_id,regions:[{start_s:0,end_s:rhythmData.duration_s,bpm,first_beat_s:first}],snap_tolerance_s:snap});
  await acceptTiming(result);
}));
$('tap-beat').addEventListener('click',()=>run(async()=>{
  const player=$('review-audio');if(player.paused||!player.currentSrc)throw new Error('Play the prepared audio before tapping at its playhead.');
  const t=player.currentTime;if(taps.length&&t<=taps[taps.length-1])throw new Error('Reset taps after seeking backward.');
  if(taps.length>=128)throw new Error('Reset taps to start another estimate.');taps.push(t);
  $('tap-status').textContent=`${taps.length} taps captured. At least four are needed.`;
  if(taps.length>=4){const estimate=await call('estimate_tap_tempo',{tap_times_s:taps});$('map-bpm').value=estimate.tempo_bpm_estimate.toFixed(3);$('map-first').value=estimate.first_tap_s.toFixed(3);$('tap-status').textContent=`${taps.length} taps · ~${estimate.tempo_bpm_estimate.toFixed(2)} BPM · ${estimate.discarded_intervals} intervals discarded. Review and save the grid explicitly.`;}
}));
$('reset-taps').addEventListener('click',()=>{taps=[];$('tap-status').textContent='Taps cleared. Play and tap at least four evenly spaced pulses.';});
async function pollAudio(version,id) {
  if(version!==reviewGeneration||audioJob!==id)return;
  try {
    const state=await call('get_job_status',{job_id:id});
    if(version!==reviewGeneration||audioJob!==id)return;
    if(state.status==='completed'){
      $('review-audio').src=state.download_url;$('review-audio').hidden=false;
      $('rhythm-status').textContent='Audio ready. Press play to review saved timing. Prepared links expire after 10 minutes.';audioJob=null;controls();return;
    }
    if(['failed','cancelled','interrupted'].includes(state.status))throw new Error(state.error||`Audio preparation ${state.status}.`);
    $('rhythm-status').textContent=`Preparing audio · ${state.status}`;audioPollTimer=setTimeout(()=>pollAudio(version,id),600);
  }catch(e){if(version===reviewGeneration){audioJob=null;controls();error(e.message);}}
}
async function prepareAudio(clicks) {
  if(clicks&&markersDirty())throw new Error('Save your timing copy before preparing matching beat clicks.');
  const version=reviewGeneration,aid=analysis.analysis_id;
  const job=await call('render_beat_preview',{analysis_id:aid,click_volume:clicks?1:0});
  if(version!==reviewGeneration||analysis?.analysis_id!==aid)return;
  audioJob=job.job_id;$('review-audio').pause();$('review-audio').removeAttribute('src');$('review-audio').load();$('review-audio').hidden=true;
  controls();await pollAudio(version,audioJob);
}
$('listen-original').addEventListener('click',()=>run(()=>prepareAudio(false)));
$('listen-clicks').addEventListener('click',()=>run(()=>prepareAudio(true)));
controls();
