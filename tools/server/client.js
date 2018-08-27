var pc = null;
var localStream = null;
var videoDevice = null;
var connectAttempts = 0,connectAttempsMax = 5;
var is_dataset = 0;
var dset_counter = 0;
var dset_name = null;
var dset_size = 8;
var use_video_checked = false;
var is_local_video = true;
var lmedia = null;
var is_mobile = false;
var mesure_tout = 5000;
var next_step_tout = 1000;
var reconnect_tout = 2000;
var transport_mode = 2; // 0 1 2 
var ws_socket = null;
var uuid_val = 1
// get DOM elements
var remoteVideo      = document.getElementById('rvideo'),
    dataChannelLog   = document.getElementById('data-channel'),
    ping             = document.getElementById('ping'),
    algorithm        = document.getElementById('algorithm'),
    photo            = document.getElementById('photo'),
    calc             = document.getElementById('calc'),
    dset             = document.getElementById('dset'),
    dset_stop        = document.getElementById('dset-stop'),
    chequer          = document.getElementById('chequer'),
    dset_nm          = document.getElementById('dset-nm'),
    uuid             = document.getElementById('uuid'),
    proc             = document.getElementById('proc-video'),
    hide             = document.getElementById('hide-local'),
    iceConnectionLog = document.getElementById('ice-connection-state'),
    iceGatheringLog  = document.getElementById('ice-gathering-state'),
    video_fps        = document.getElementById("video-fps"),
    use_video        = document.getElementById('use-video'),
    signalingLog     = document.getElementById('signaling-state'),
    answer_sdp       = document.getElementById('answer-sdp'),
    offer_sdp        = document.getElementById('offer-sdp');
    

function get_fps() {
var i = video_fps.options.selectedIndex;
  return video_fps.options[i].text;
} 
function reconnect() {
     if (connectAttempts < connectAttempsMax) {
         connectAttempts++;
         dataChannelLog.textContent = 'Try to connect again '+connectAttempts+'\n' + dataChannelLog.textContent;
         cleanIceContext();
         
         make_dset_stop("",false);
         makeConnection();
     }
}
function addListeners(pc) {
    // register some listeners to help debugging
    pc.addEventListener('icegatheringstatechange', function() {
            iceGatheringLog.textContent += ' -> ' + pc.iceGatheringState;
        }, false);
    iceGatheringLog.textContent = pc.iceGatheringState;

    pc.addEventListener('iceconnectionstatechange', function() {
            iceConnectionLog.textContent += ' -> ' + pc.iceConnectionState;
            if (pc.iceConnectionState == 'failed') {
              dataChannelLog.textContent = 'IceConnectionState failed - close connection\n' + dataChannelLog.textContent;
              //remoteVideo.pause();
              hangup(false);
              //if (connectAttempts == 0) {
                  setTimeout(function() {
                    dataChannelLog.textContent = 'Reconnect:\n' + dataChannelLog.textContent;
                    reconnect();
                   }, reconnect_tout);
              //}

              
            }
        }, false);
    iceConnectionLog.textContent = pc.iceConnectionState;

    pc.addEventListener('signalingstatechange', function() {
            signalingLog.textContent += ' -> ' + pc.signalingState;
        }, false);
    signalingLog.textContent = pc.signalingState;

    // connect audio / video
    pc.addEventListener('track', function(evt) {
            dataChannelLog.textContent += 'EVENT track' + evt.track.label+'\n';
            if (evt.track.kind == 'video') {
                dataChannelLog.textContent += 'track:video,label.' + evt.track.label+'\n';
                if (remoteVideo.srcObject != evt.streams[0]) {
                    remoteVideo.srcObject = evt.streams[0];
                }
                remoteVideo.onloadedmetadata = function(e) {
                remoteVideo.play();
                  /*
                  if(hide.checked)
                  {
                      document.getElementById('video').style.display = 'none';
                  }*/
                };
            } else document.getElementById('audio').srcObject = evt.streams[0];
        });
}
function cleanIceContext () {
iceGatheringLog.textContent = '';
iceConnectionLog.textContent = '';
signalingLog.textContent     = '';
}
// data channel
var dc = null, dcInterval = null;
var captureDevice = null;
var show_photo = false;

//dataChannelLog.textContent = 'Agent:'+navigator.userAgent;

function dc_send_blob(oper,blob) {
 var chunkSize = 16384;
 var offset = 0;
      dataChannelLog.textContent = 'Send blob '+oper+' \n' + dataChannelLog.textContent;
      dc.send(oper + " " + blob.size);
      var sliceFile = function(offset) {
        var reader = new window.FileReader();
        reader.onload = (function() {
        return function(e) {
        dc.send(e.target.result);
        if (blob.size > offset + e.target.result.byteLength) {
          window.setTimeout(sliceFile, 0, offset + chunkSize);
        } else {
            dc.send("photoeof");
        }
        
       };
       })(blob);
       var slice = blob.slice(offset, offset + chunkSize);
       reader.readAsArrayBuffer(slice);
      };
      sliceFile(0);
      
}
function processPhoto(blob,oper) {
  //photo.src = window.URL.createObjectURL(blob);
  //photo.style.display = 'inline-block' ;
  dataChannelLog.textContent = oper +' SIZE:'+blob.size+'\n' + dataChannelLog.textContent;
  if (is_channel_ready()) {
      channel_send_blob(oper,blob);
  }
}
function processPhotoExif(blob) {
    photo.src = window.URL.createObjectURL(blob);
    photo.style.display = 'inline-block' ;
    processPhoto(blob,"photo");
}
function calcLensByPhoto(blob) {
    processPhoto(blob,"calc");
}
function distByPhoto(blob) {
    processPhoto(blob,"calibr");
}
function catchPhoto(err) {
  //photo.src = "";
  dataChannelLog.textContent = 'Cant get photo:'+err+'\n' + dataChannelLog.textContent;
  // cancel dataset 
  on_dset_cancel();
}
function get_photo() {
    if(photo.style.display == 'none') {
         if (captureDevice != null) {
                dataChannelLog.textContent = 'Try get photo \n' + dataChannelLog.textContent;
                captureDevice.takePhoto().then(processPhotoExif).catch(catchPhoto);
         }
    } else photo.style.display = 'none';
}
function sendCmdByPost(cmd) { 
    // get result
         var xhr1 = new XMLHttpRequest();
          xhr1.responseType = 'json';
          xhr1.open("GET", '/result?uid='+uuid_val+'&dsetnm='+dset_name+'&cmd='+cmd, true);
          xhr1.onload = function(e) {
             if (this.status == 200) {
               var resp = this.response;
               dataChannelLog.textContent = 'get response '+JSON.stringify(resp)+'\n' + dataChannelLog.textContent;
               if (resp.status) {
                   dset_nm.value = "";
               }
             }
          };
          xhr1.send();

}
function sendBlobByPost(blob,dsetnm,oper) {
var xhr = new XMLHttpRequest();
  
  xhr.open("POST", '/mesure?uid='+uuid_val+'&dsetnm='+dsetnm+'&cmd='+oper, true);

  xhr.onreadystatechange = function() {
      if (this.readyState != 4) return;
      dataChannelLog.textContent = 'POST '+this.responseText+'\n' + dataChannelLog.textContent;
      let resp = JSON.parse(this.responseText);
      if (resp.ret == 0) {
        var cnt = resp.cnt;
        if (cnt < dset_size) { // ask next photo
         setTimeout(function() {
            next_dset_item();
         }, next_step_tout);
         
        } else // stop 

               on_dset_stop();
              
      }
      //getMesureResult();
  };
  xhr.upload.onprogress = function(e) {
    if (e.lengthComputable) {
      
      dataChannelLog.textContent = 'Send .. '+ ((e.loaded / e.total) * 100) +'\n' + dataChannelLog.textContent;
    }
  };
  dataChannelLog.textContent = 'Send photo\n' + dataChannelLog.textContent;
  var formData = new FormData();
  formData.append('blob', blob);
  xhr.send(formData);
}

// send photo by POST
function post_photo() {
    getPhotoForPost =  function (blob) {
        if (blob) {
          sendBlobByPost(blob,'first','calibr'); 
          //getMesureResult(); 
        } else dataChannelLog.textContent = 'Cant get photo\n' + dataChannelLog.textContent;
        
    
   }
   if (captureDevice != null) {
       dataChannelLog.textContent = 'Try get photo for post\n' + dataChannelLog.textContent;
       captureDevice.takePhoto().then(getPhotoForPost).catch(catchPhoto);
   }
   
    
}

function on_calc_by_photo() {
         make_dset("dset",3,"");
 
}
// make mesure by single photo

function calc_by_photo() {
         if (captureDevice != null && (is_dataset != 0)) {
             var attempt = 4;
             var calcCatchPhoto = function(err) {
               dataChannelLog.textContent = 'Cant get photo:'+err+'\n' + dataChannelLog.textContent;
               if(--attempt > 0) {
                  captureDevice.takePhoto().then(calcLensByPhoto).catch(calcCatchPhoto);
               } else {
                     on_dset_cancel();     
               }
             }
             dataChannelLog.textContent = 'Try calc by photo \n' + dataChannelLog.textContent;
             captureDevice.takePhoto().then(calcLensByPhoto).catch(calcCatchPhoto);
                
                
         }
}

function dist_by_photo() {
         if (captureDevice != null && (is_dataset != 0)) {
             var attempt = 4;
             var distCatchPhoto = function(err) {
               dataChannelLog.textContent = 'Cant get photo:'+err+' State='+ videoDevice.readyState +'\n' + dataChannelLog.textContent;
               if(--attempt > 0) {
                  captureDevice.takePhoto().then(distByPhoto).catch(distCatchPhoto);
               } else {
                     on_dset_cancel();     
               }
             }
             dataChannelLog.textContent = 'Distortion by photo \n' + dataChannelLog.textContent;
             captureDevice.takePhoto().then(distByPhoto).catch(distCatchPhoto);
                
                
         }
}
function negotiate() {
    return pc.createOffer().then(function(offer) {
        return pc.setLocalDescription(offer);
    }).then(function() {
        // wait for ICE gathering to complete
        return new Promise(function(resolve) {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function() {
        var offer = pc.localDescription;
        if (offer_sdp) { offer_sdp.textContent = offer.sdp;}
          return fetch('/offer', {
            body: JSON.stringify(offer),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
          }).catch(function(error) {
               dataChannelLog.textContent = '- Cant fetch offer\n' + dataChannelLog.textContent;
          });
            
        
        
    }).then(function(response) {
        return response.status == 200 ? response.json() : "{}";
        
        
    }).then(function(answer) {
        if (answer_sdp) { answer_sdp.textContent = offer.sdp;}
        
        return (answer != "{}") ? pc.setRemoteDescription(answer) : false;
    });
}

function on_connect_done() {
    document.getElementById('uuid').style.display = 'inline-block';
    document.getElementById('foruuid').style.display = 'inline-block';
    dset.style.display = 'inline-block';
    calc.style.display = 'inline-block';
    chequer.style.display = 'inline-block';
}

function makeConnection() {
  //dataChannelLog.textContent = '';
  pc = new RTCPeerConnection(); // create new one
  if(pc) addListeners(pc);
  else {
    dataChannelLog.textContent = '- can not create RTCPeerConnection\n' + dataChannelLog.textContent;
  }
  if (document.getElementById('use-datachannel').checked) {
        dc = pc.createDataChannel('chat');
        dc.onclose = function() {
            clearInterval(dcInterval);
            dataChannelLog.textContent = '- connection closed\n' + dataChannelLog.textContent;
            hangup(false);
           setTimeout(function() {
                dataChannelLog.textContent = 'Reconnect:\n' + dataChannelLog.textContent;
                reconnect();
               }, reconnect_tout);
           };
        dc.onopen = function() {
            dataChannelLog.textContent = '';
            dataChannelLog.textContent += '- connection opened\n';
            //process = proc.checked;
            algor   = algorithm.checked;
            /*
            if (process) {
              dc.send("process"); // switch on
            }*/
            if (algor) {
              dc.send("algorithm");
            }
            on_connect_done();
         
            dcInterval = setInterval(function() {
                var message = 'Ping';
                if (ping.checked) {
                    dataChannelLog.textContent = '> ' + message + '\n' + dataChannelLog.textContent;
                    dc.send(message);
                }
                /*
                if(process != proc.checked) {
                     dc.send("process");
                     process = proc.checked
                }*/
                if(algor != algorithm.checked) {
                     dc.send("algorithm");
                     algor = algorithm.checked
                }
            }, 1000);
        };
        dc.onmessage = function(evt) {
            if (evt.data != "photo") dataChannelLog.textContent = '< ' + evt.data + '\n' + dataChannelLog.textContent;
            if (evt.data == "video") {
                var streams = pc.getRemoteStreams();
                for (var stream of streams) {
                    dataChannelLog.textContent = '< stream' + stream.id + '\n' + dataChannelLog.textContent;
                       
                }
            } else if (evt.data == "photo") {
                if (captureDevice != null && show_photo) {
                    psets = captureDevice.getPhotoSettings()
                    dataChannelLog.textContent = 'Try get photo'+JSON.stringify(psets)+'\n' + dataChannelLog.textContent;
                    captureDevice.takePhoto().then(processPhoto).catch(catchPhoto);
                }
            } else if (evt.data.substr(0,5) == "AVG::") {
                  
                dataChannelLog.textContent = '< STOP DATASET' + '\n' + dataChannelLog.textContent;
                //on_dset_stop();
            } else if (evt.data.substr(0,10) == "dataseteof") { // dataseteof num=
                var cnum = evt.data.substr(15); // take num
                if (cnum != 0) { // clear dataset name
                   dset_nm.value = "";
                }
                on_dset_stop();
            }else if (evt.data == "nextcalc") {
                  
                dataChannelLog.textContent = 'get next '+dset_counter+' photo\n' + dataChannelLog.textContent;
                next_dset_item();
                
            }
        };
    }
    if (localStream != null) {
        localStream.getTracks().forEach(function(track) {
                    dataChannelLog.textContent += 'track.' + track.kind + ' label.' + track.label+'\n';
                    /*
                    sets = track.getSettings();
                    caps = track. getCapabilities();
                    val = JSON.stringify(sets);
                    cval = JSON.stringify(caps);
                    dataChannelLog.textContent += 'setting=' + val +'\n';
                    dataChannelLog.textContent += 'caps=' + cval +'\n';
                    if (sets.focusDistance ) {
                        dataChannelLog.textContent += 'focus=' + sets.focusDistance +'\n';
                    }
                    */
                    if (track.kind == "video") {
                        if (use_video_checked) {
                            document.getElementById('rvideo').style.display = 'block';
                            try {
                              videoDevice = track;//stream.getVideoTracks()[0];
                              // Check if this device supports a picture mode...
                              //captureDevice = new ImageCapture(videoDevice);
                              /*if (captureDevice) {
                                 dataChannelLog.textContent += 'Try get photo'+'\n';
                                 captureDevice.takePhoto().then(processPhoto);//.catch(stopCamera);
                              }*/
                        
                            } catch (err) {
                                dataChannelLog.textContent = 'Cant get photo:'+err+'\n' + dataChannelLog.textContent;
                            }
                            pc.addTrack(track, localStream);
                        }

                    } else 
                           pc.addTrack(track, localStream);
                });
    }
    negotiate();

}
function closeConnection(pc) {
    if (pc == null) {
      return;
    }
    cleanIceContext();
    // close data channel
    if (dc) {
        dc.close();
    }
    // close peer connection
    setTimeout(function() {
        pc.close();
        pc = null;
    }, 500);
}
function call() {
 //document.getElementById('hangup').style.display = 'inline-block';
 //document.getElementById('call').style.display = 'none';
 makeConnection();
}
function hangup(mode = true) {
 //document.getElementById('hangup').style.display = 'none';
 //document.getElementById('call').style.display = 'inline-block'; 
 uuid.style.display = 'none';
 document.getElementById('foruuid').style.display = 'none';
 dset.style.display = 'none';
 dset_stop.style.display = 'none';
 calc.style.display = 'none';
 chequer.style.display = 'none';
 if (mode) {
     closeConnection(pc);
 }
 /*if (hide.checked) {
     document.getElementById('video').style.display = 'block';
 }*/
}
function on_hangup() {
  connectAttempts = connectAttempsMax;
  hangup();
}

function on_call() {
  connectAttempts = 0;
  switch(transport_mode) {
  case 0: call();break;
  case 1: ws_call();break;
  case 2: post_call();break;
  } 
}
function is_channel_ready() {
  switch(transport_mode) {
  case 0: return dc != null;
  case 1: return true;
  case 2: return true;
  default: return false;
  }
}
function channel_send(cmd,arg) {
switch(transport_mode) {
  case 0: dc.send(cmd+' '+arg); break;
  case 1:  break;
  case 2: post_send(cmd,arg); break;
  }
    
}

function channel_send_blob(cmd,blob) {

switch(transport_mode) {
  case 0: dc_send_blob(cmd,blob); break;
  case 1:  break;
  case 2: post_send_blob(cmd,blob); break;
  }
    
}
function on_uid() {
   uuid.innerHTML = "";
   uuid_val = uuid.value;
   if (dc) {
       // send uid for calibr session
       dc.send("userId "+uuid.value);


   }
}
function on_hide()
{
    document.getElementById('video').style.display = hide.checked ? 'none' : 'block';
   
}
function set_dset_style(dset_mode,val) {
     switch(dset_mode) {
     case 1:dset.style.display = val;break;
     case 2:chequer.style.display = val;break;
     case 3:calc.style.display = val;break;
     }
}
function make_dset(dset_type,dset_mode,dset_name)
{
 
 if (is_channel_ready()) {
     set_dset_style(dset_mode,"none");
     dset_stop.style.display = 'inline-block'; 
     
     channel_send(dset_type,dset_name);
     is_dataset = dset_mode;
     if (is_mobile) {
         if (lmedia.requestFullscreen) {
           lmedia.requestFullscreen();
         } else if (lmedia.mozRequestFullScreen) {
             lmedia.mozRequestFullScreen();
         } else if (lmedia.webkitRequestFullscreen) {
             lmedia.webkitRequestFullscreen();
         } else if (lmedia.msRequestFullscreen) { 
             lmedia.msRequestFullscreen();
         }
     }
 }
}
function on_dset()
{
  
  make_dset("dset",1,dset_nm.value);
}
function exitFullScreen() {
  if (is_mobile ) {
     if (document.exitFullscreen) {
      document.exitFullscreen();
     } else if (document.msExitFullscreen) {
      document.msExitFullscreen();
     } else if (document.mozCancelFullScreen) {
      document.mozCancelFullScreen();
     } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen();
     }
  }
}
function make_dset_stop(cmd ,mode=true)
{
 if (is_dataset != 0) {
     if(mode) set_dset_style(is_dataset,"inline-block");
     dset_stop.style.display = 'none';
     is_dataset = 0; 
     dset_counter = 0;
     if (is_channel_ready() && cmd != "") {
         //dc.send(cmd);
         channel_send(cmd,'');
     }
     exitFullScreen();
 }
}
function on_dset_stop()
{
  dataChannelLog.textContent = '< DATASETEOF\n' + dataChannelLog.textContent;
  make_dset_stop("dset-stop");
}
function on_dset_cancel() {
  make_dset_stop("dsetcancel");
}
function calculate() {

}

function on_chequer() {
    
    make_dset("chequer",2,dset_nm.value);
}
function next_dset_item() {
     
     switch(is_dataset) {
      case 1:case 3:dset_counter++;calc_by_photo();break;
      case 2:dset_counter++;dist_by_photo();break;
     }
}


function onPause(e) {
var ev = e;
 lmedia.play();
 /*lmedia.addEventListener("timeupdate", function() {
    
 }, false);*/
 if(dset_counter == 0 && is_dataset != 0) {
    dataChannelLog.textContent = 'Pause '+mesure_tout+'ms before dataset starting:\n' + dataChannelLog.textContent;
    setTimeout(function() {
        
         dataChannelLog.textContent = 'Start dataset:\n' + dataChannelLog.textContent;
         next_dset_item();
        
    }, mesure_tout);
 }
 
 return true;
}

function onPlay(e) {
var ev = e;
//dataChannelLog.textContent = 'press play:\n' + dataChannelLog.textContent;
}
function getUserMediaFunc() {
  // Note: Opera builds are unprefixed.
  return navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia || navigator.msGetUserMedia;
}
function start() {
    document.getElementById('start').style.display = 'none';
    uuid.onchange = on_uid;
    lmedia = document.getElementById('video');
    lmedia.addEventListener("pause", onPause, false);
    lmedia.addEventListener("play", onPlay, false);
    
    
    is_mobile = navigator.userAgent.indexOf('Mobile') != -1
    var constraints = {
        audio: false, //document.getElementById('use-audio').checked,
        video: is_local_video ? { width: 1280, height: 720,facingMode:is_mobile ? { exact: "environment" } : {} 
                            ,frameRate: { ideal: get_fps()
                                          //, max: get_fps() 
                             }
        } : false
    };

    if (constraints.audio || constraints.video) {
        if (constraints.video) {
            document.getElementById('video').style.display = 'block';
        }
        try {
            
            navigator.mediaDevices.getUserMedia(constraints).then(function(stream) {
            localStream = stream;
            
            try {
                      videoDevice = stream.getVideoTracks()[0];
                      // Check if this device supports a picture mode...
                      captureDevice = new ImageCapture(videoDevice);
                      //document.getElementById('get-photo').style.display = 'inline-block';
                      
                
            } catch (err) {
                        dataChannelLog.textContent = 'Cant get ImageCapture:'+err+'\n' + dataChannelLog.textContent;
            }
            /*
            stream.getTracks().forEach(function(track) {
                dataChannelLog.textContent += 'track.' + track.kind + ' label.' + track.label+'\n';
                pc.addTrack(track, stream);
            });*/
            var video = document.querySelector('video');
            // Older browsers may not have srcObject
            if ("srcObject" in video) {
              video.srcObject = stream;
            } else {
              // Avoid using this in new browsers, as it is going away.
              video.src = window.URL.createObjectURL(stream);
            }
            video.onloadedmetadata = function(e) {
              video.play();
              //document.getElementById('call').style.display = 'inline-block';
              on_call();
            };
            //makeConnection();
            return ; //negotiate();
        }).catch(function(err) {
            dataChannelLog.textContent = 'ERR0:'+err+'\n' + dataChannelLog.textContent;
        });
            
        } catch (err) {
            dataChannelLog.textContent = 'ERR1:'+err+'\n' + dataChannelLog.textContent;
        }
        
    } else {
        document.getElementById('call').style.display = 'inline-block';
    }
    
    document.getElementById('stop').style.display = 'inline-block';
}

function stop() {
    document.getElementById('stop').style.display = 'none';
    document.getElementById('start').style.display = 'inline-block';
    //document.getElementById('hangup').style.display = 'none';
    //document.getElementById('call').style.display = 'none';
    //photo.style.display = 'none';
    //calc.style.display = 'none';
    if (localStream != null) {
        pc.getSenders().forEach(function(sender) {
            sender.track.stop();
        });
    }
    on_hangup();
    //closeConnection(pc);
    // close audio / video
    

}
/*
* wsock mode
*/
function ws_call() {
    var currentLocation = window.location;
    dataChannelLog.textContent = 'Use websocket channel.\n' + dataChannelLog.textContent;
    ws_socket = new WebSocket("wss://"+currentLocation.host+"/wss");
    return;
}

// POST transport
function post_call() {
   dataChannelLog.textContent = 'Use POST channel.\n' + dataChannelLog.textContent;
   on_connect_done();

}
function post_send(cmd,arg) {
  switch (cmd) {
  case 'dset-stop':
      // ask result
      sendCmdByPost(cmd);
      break
  case 'calc':case 'dset':
      dset_name = arg;
      if (arg == '') {
        dset_name = 'mdefault';
      }
      break;
  }
   
}
function post_send_blob(oper,blob) {
    sendBlobByPost(blob,dset_name,oper);

}
