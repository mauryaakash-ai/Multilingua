const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();let recordings=0,release,attempts=0,stopped=0,delay;
const context={console,Blob,Map,performance,URLSearchParams,location:{search:""},localStorage:{getItem(){return null},setItem(){}},URL:{createObjectURL(){return "blob:recording"},revokeObjectURL(){}},window:{addEventListener(){}},document:{getElementById(id){if(!elements.has(id))elements.set(id,{value:id==='duration'?'15':id==='language'?'hi':'latentsync',pause(){},load(){},addEventListener(){},play(){return Promise.resolve()},paused:false});return elements.get(id)}},setInterval(){return 1},clearInterval(){},setTimeout(fn,ms){if(ms===15000){delay=ms;return 1}queueMicrotask(fn);return 1},clearTimeout(){},fetch:async(url,opts)=>{attempts++;if(opts)assert.equal(opts.headers['X-Lipsync-Model'],'latentsync');return attempts===1?{status:429}: {status:202,ok:true,json:async()=>({id:'test',status:'complete',compute_seconds:1,source_seconds:15})}},MediaRecorder:class{static isTypeSupported(){return true}constructor(){recordings++;this.mimeType='video/webm';this.state='inactive'}start(){}stop(){}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('web/index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1],context);
(async()=>{
 await vm.runInContext('submit(new Blob(["clip"]),0)',context);assert.equal(attempts,3);assert(!elements.get('status').textContent.includes('Stopped'));
 context.waitForJob=new Promise(r=>release=r);context.track={stop(){stopped++}};
 vm.runInContext('submit=()=>waitForJob;running=true;stream={getTracks:()=>[track]};chunk();recorder.ondataavailable({data:new Blob(["clip"])});recordingDone=recorder.onstop()',context);
 assert.equal(delay,15000);assert.equal(recordings,1);assert.equal(stopped,1);
 assert.equal(elements.get('source').srcObject,null);assert.equal(elements.get('source').src,'blob:recording');release();await context.recordingDone;assert.equal(recordings,1,'one-shot capture must not silently restart');
 console.log('PASS: model header, queue retry, duration and camera shutdown');
})().catch(e=>{console.error(e);process.exitCode=1});
