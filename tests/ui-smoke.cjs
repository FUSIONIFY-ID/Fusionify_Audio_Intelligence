// Browser integration runs on a host that permits Chromium, including GitHub Actions.
const {chromium} = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {spawn, spawnSync} = require('child_process');
const crypto = require('crypto');

(async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(),'fai-ui-'));
  const output = process.env.FAI_QA_ARTIFACTS || path.join(root,'screenshots');
  fs.mkdirSync(output,{recursive:true});
  const token = crypto.randomBytes(48).toString('base64url');
  const python = process.env.PYTHON || 'python';
  const fixture = `from pathlib import Path\nimport sys,numpy as np\nfrom PIL import Image\nfrom scipy.io import wavfile\nr=Path(sys.argv[1]);sr=22050;y=np.zeros(sr*4,dtype=np.float32)\nt=np.arange(800)/sr;c=.65*np.sin(2*np.pi*180*t)*np.exp(-t*110)\nfor b in np.arange(.4,3.9,60/128):\n k=int(b*sr);y[k:k+len(c)]+=c[:len(y)-k]\nwavfile.write(r/'track.wav',sr,y)\nImage.new('RGB',(800,600),(25,70,150)).save(r/'visual.png')\n`;
  const made = spawnSync(python,['-c',fixture,root],{encoding:'utf8'});
  if(made.status) throw new Error(made.stderr);
  const server = spawn(python,['-m','fusionify_audio.cli','serve-http','--port','8765'],{
    env:{...process.env,FAI_MEDIA_ROOT:root,FAI_STATE_ROOT:path.join(root,'state'),FAI_API_TOKEN:token},stdio:['ignore','ignore','pipe']});
  let serverLog='';server.stderr.on('data',chunk=>serverLog+=chunk.toString());
  let browser;
  try {
    let ready=false;
    for(let i=0;i<100;i++) {
      try { if((await fetch('http://127.0.0.1:8765/healthz')).ok){ready=true;break;} } catch {}
      if(server.exitCode!==null) throw new Error('Server failed: '+serverLog);
      await new Promise(r=>setTimeout(r,100));
    }
    if(!ready) throw new Error('Server startup timeout');
    browser=await chromium.launch({headless:true});
    const page=await browser.newPage({viewport:{width:1505,height:1045}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
    await page.goto('http://127.0.0.1:8765');
    if(await page.title()!=='Fusionify Audio Intelligence')throw new Error('Wrong page identity');
    await page.getByRole('heading',{name:'Your music. Your next edit.'}).waitFor();
    await page.screenshot({path:path.join(output,'desktop-concept-size.png'),fullPage:true});
    await page.setViewportSize({width:1440,height:1000});
    await page.screenshot({path:path.join(output,'desktop-empty.png'),fullPage:true});
    await page.locator('#token').fill(token);await page.locator('#connect').click();
    await page.getByRole('button',{name:'Disconnect',exact:true}).waitFor();
    if(await page.locator('#token').inputValue())throw new Error('Token remains in the visible input');
    await page.locator('#files').setInputFiles([path.join(root,'track.wav'),path.join(root,'visual.png')]);
    await page.locator('#upload-status').filter({hasText:'Uploaded.'}).waitFor();
    const aid=await page.locator('#audio option').filter({hasText:'track.wav'}).getAttribute('value');
    await page.locator('#audio').selectOption(aid);
    await page.locator('#analysis').filter({hasText:'candidate beats'}).waitFor();
    await page.locator('[data-visual]').check();
    await page.locator('#title').fill('Fusionify creator test');
    await page.locator('#aspect').selectOption('16:9');await page.locator('#resolution').selectOption('480');
    await page.locator('#start').fill('0.5');await page.locator('#duration').fill('2');
    await page.locator('#save').click();await page.locator('#project-status').filter({hasText:'Saved revision 1'}).waitFor();
    await page.locator('#preview').click();
    await page.locator('#job-status').filter({hasText:'Completed'}).waitFor({timeout:60000});
    await page.waitForFunction(()=>document.querySelector('#video').readyState>=1);
    const metadata=await page.locator('#video').evaluate(v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight}));
    if(metadata.width!==854||metadata.height!==480||Math.abs(metadata.duration-2)>.08)throw new Error('Video metadata mismatch '+JSON.stringify(metadata));
    await page.locator('#video').evaluate(async v=>{v.muted=true;await v.play();});
    await page.waitForFunction(()=>document.querySelector('#video').currentTime>.2);
    await page.locator('#video').evaluate(v=>{v.pause();v.currentTime=.5;});
    await page.waitForFunction(()=>!document.querySelector('#video').seeking && document.querySelector('#video').readyState>=2);
    await page.locator('#export-json').click();await page.locator('#export-link').waitFor({state:'visible'});
    const exported=await (await page.request.get(await page.locator('#export-link').getAttribute('href'))).json();
    if(exported.options.duration_s!==2)throw new Error('Export mismatch');
    await page.locator('#caption').fill('Revision verified');await page.locator('#save').click();
    await page.locator('#project-status').filter({hasText:'Saved revision 2'}).waitFor();
    await page.screenshot({path:path.join(output,'desktop-result.png'),fullPage:true});
    const desktopOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    await page.getByRole('button',{name:'Disconnect',exact:true}).click();
    await page.getByRole('button',{name:'Connect',exact:true}).waitFor();
    if(await page.locator('#library li').count())throw new Error('Disconnected page retained the asset list');
    if(await page.locator('#video').getAttribute('src'))throw new Error('Disconnected page retained a preview URL');
    const mobile=await browser.newPage({viewport:{width:390,height:844}});
    mobile.on('pageerror',e=>errors.push(e.message));await mobile.goto('http://127.0.0.1:8765');
    await mobile.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
    const mobileOverflow=await mobile.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    if(errors.length||desktopOverflow||mobileOverflow)throw new Error(JSON.stringify({errors,desktopOverflow,mobileOverflow}));
    console.log(JSON.stringify({status:'PASS',flow:'connect, upload music/photo, analyze, save, montage preview, media metadata, export, revision',
      metadata,desktopOverflow,mobileOverflow,pageErrors:errors,viewports:['1505x1045','1440x1000','390x844']}));
  } finally {
    if(browser)await browser.close();server.kill('SIGTERM');
    await new Promise(resolve=>{if(server.exitCode!==null)return resolve();server.once('exit',resolve);setTimeout(()=>{server.kill('SIGKILL');resolve();},10000).unref();});
    fs.rmSync(root,{recursive:true,force:true});
  }
})().catch(e=>{console.error(e);process.exit(1);});
