'use strict';
const $ = id => document.getElementById(id);
let token = '', assets = [], analysis = null, project = null, projectAnalysis = null;
let savedOptions = '', busy = 0, currentJob = null, currentRenderRevision = null, generation = 0, pollTimer = null;

function error(message) { $('error').textContent = message || ''; $('error').hidden = !message; }
function controls() {
  $('connect').disabled = busy > 0;
  for (const id of ['choose','save','preview','render']) $(id).disabled = !token || busy > 0 || (['preview','render'].includes(id) && !!currentJob);
  $('cancel').disabled = !currentJob;
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
$('audio').addEventListener('change', () => { analysis=null;generation++;run(ensureAnalysis); });
function options() {
  if (!$('project-form').reportValidity()) throw new Error('Check the highlighted project fields.');
  return {title:$('title').value,caption:$('caption').value,style:$('style').value,intensity:$('intensity').value,
    aspect:$('aspect').value,resolution:Number($('resolution').value),music_in_s:Number($('start').value),
    duration_s:$('duration').value === '' ? null : Number($('duration').value),
    asset_ids:[...document.querySelectorAll('[data-visual]:checked')].map(el => el.value)};
}
async function save() {
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
  try {
    const job = await call('get_job_status',{job_id:currentJob});
    $('progress').value = job.progress || 0; $('job-status').textContent = `${job.status.charAt(0).toUpperCase()+job.status.slice(1)}${job.status === 'running' ? ` · ${Math.round(100*(job.progress||0))}%` : ''}`;
    if (job.status === 'completed') {
      $('job-status').textContent = `Completed · revision ${currentRenderRevision}`;
      $('preview-empty').hidden = true; $('video').hidden = false; $('video').src = job.download_url;
      $('download').href = job.download_url; $('download').hidden = false;
      currentJob=null;controls();return;
    }
    if (['failed','cancelled','interrupted'].includes(job.status)) { currentJob=null;controls();if(job.error)error(job.error);return; }
    pollTimer = setTimeout(poll,1000);
  } catch (e) { currentJob=null;controls();error(e.message); }
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
controls();
