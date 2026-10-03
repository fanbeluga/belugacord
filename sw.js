const CACHE='belugacord-2.8-v1';
const ASSETS=['/','/manifest.json'];

self.addEventListener('install',function(e){
  e.waitUntil(caches.open(CACHE).then(function(c){return c.addAll(ASSETS);}));
  self.skipWaiting();
});

self.addEventListener('activate',function(e){
  e.waitUntil(caches.keys().then(function(keys){
    return Promise.all(keys.filter(function(k){return k!==CACHE;}).map(function(k){return caches.delete(k);}));
  }));
  self.clients.claim();
});

self.addEventListener('fetch',function(e){
  var url=new URL(e.request.url);
  if(url.pathname.startsWith('/api/')||url.pathname.startsWith('/ws')){
    return;
  }
  e.respondWith(
    fetch(e.request).catch(function(){
      return caches.match(e.request).then(function(r){return r||caches.match('/');});
    })
  );
});