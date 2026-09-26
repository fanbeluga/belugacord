self.addEventListener('install',e=>{
  self.skipWaiting();
});

self.addEventListener('activate',e=>{
  e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch',e=>{
  // Пропускаем всё через сеть (никакого кэша — чтобы апдейты сразу прилетали)
  e.respondWith(fetch(e.request).catch(function(){return caches.match(e.request);}));
});

// Пуш-уведомления (на будущее)
self.addEventListener('push',e=>{
  var data={title:'Belugacord',body:'Новое сообщение'};
  try{if(e.data)data=e.data.json();}catch(err){}
  e.waitUntil(self.registration.showNotification(data.title,{
    body:data.body,
    icon:'/uploads/icon.png',
    badge:'/uploads/icon.png',
    vibrate:[200,100,200]
  }));
});

self.addEventListener('notificationclick',e=>{
  e.notification.close();
  e.waitUntil(clients.matchAll({type:'window'}).then(function(clientList){
    for(var i=0;i<clientList.length;i++){
      var c=clientList[i];
      if(c.url.includes(self.registration.scope)&&'focus' in c)return c.focus();
    }
    if(clients.openWindow)return clients.openWindow('/');
  }));
});