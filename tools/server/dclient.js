var pc = null;
var localStream = null;
var videoDevice = null;
var connectAttempts = 0,connectAttempsMax = 5;
var is_dataset = 0;

var is_local_video = true;
var lmedia = null;
var is_mobile = false;
var mesure_tout = 5000;
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
    signalingLog     = document.getElementById('signaling-state');
    

function get_fps() {
var i = video_fps.options.selectedIndex;
  return video_fps.options[i].text;
} 
function reconnect() {
     if (connectAttempts < connectAttempsMax) {
         connectAttempts++;
         dataChannelLog.textContent = 'Try to connect again\n' + dataChannelLog.textContent;
         signalingLog.textContent = '';
         iceGatheringLog.textContent = '';
         call();
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
              remoteVideo.pause();
              hangup();
              reconnect();
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
                  if(hide.checked)
                  {
                      document.getElementById('video').style.display = 'none';
                  }
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

function processPhoto(blob,oper) {
  //photo.src = window.URL.createObjectURL(blob);
  //photo.style.display = 'inline-block' ;
  dataChannelLog.textContent = oper +' SIZE:'+blob.size+'\n' + dataChannelLog.textContent;
  if (dc != null) {
      var chunkSize = 16384;
      var offset = 0;
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
    processPhoto(blob,"dist");
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

function on_calc_by_photo() {
         make_dset("dset ",1,"");
 
}
// make mesure by single photo

function calc_by_photo() {
         if (captureDevice != null && (calc.style.display != 'none')) {
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
         if (captureDevice != null && (calc.style.display != 'none')) {
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
        document.getElementById('offer-sdp').textContent = offer.sdp;
        return fetch('/offer', {
            body: JSON.stringify(offer),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function(response) {
        return response.json();
    }).then(function(answer) {
        document.getElementById('answer-sdp').textContent = answer.sdp;
        return pc.setRemoteDescription(answer);
    });
}
function makeConnection() {
  dataChannelLog.textContent = '';
  pc = new RTCPeerConnection(); // create new one
  addListeners(pc);
  if (document.getElementById('use-datachannel').checked) {
        dc = pc.createDataChannel('chat');
        dc.onclose = function() {
            clearInterval(dcInterval);
            dataChannelLog.textContent = '- connection closed\n' + dataChannelLog.textContent;
            hangup();
            reconnect();
        };
        dc.onopen = function() {
            dataChannelLog.textContent += '- connection opened\n';
            process = proc.checked;
            algor   = algorithm.checked;
            
            if (process) {
              dc.send("process"); // switch on
            }
            if (algor) {
              dc.send("algorithm");
            }
            document.getElementById('uuid').style.display = 'inline-block';
            document.getElementById('foruuid').style.display = 'inline-block';
            dset.style.display = 'inline-block';
            calc.style.display = 'inline-block';
            chequer.style.display = 'inline-block';

            dcInterval = setInterval(function() {
                var message = 'Ping';
                if (ping.checked) {
                    dataChannelLog.textContent = '> ' + message + '\n' + dataChannelLog.textContent;
                    dc.send(message);
                }
                if(process != proc.checked) {
                     dc.send("process");
                     process = proc.checked
                }
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
                dataChannelLog.textContent = '< DATASETEOF\n' + dataChannelLog.textContent;
                on_dset_stop();
            }else if (evt.data == "nextcalc") {
                  
                dataChannelLog.textContent = 'get next photo\n' + dataChannelLog.textContent;
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
                        if (use_video.checked) {
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
 document.getElementById('hangup').style.display = 'inline-block';
 document.getElementById('call').style.display = 'none';
 makeConnection();
}
function hangup() {
 document.getElementById('hangup').style.display = 'none';
 document.getElementById('call').style.display = 'inline-block'; 
 uuid.style.display = 'none';
 document.getElementById('foruuid').style.display = 'none';
 dset.style.display = 'none';
 dset_stop.style.display = 'none';
 calc.style.display = 'none';
 chequer.style.display = 'none';

 closeConnection(pc);
 if (hide.checked) {
     document.getElementById('video').style.display = 'block';
 }
}
function on_hangup() {
  connectAttempts = connectAttempsMax;
  hangup();
}
function on_call() {
  connectAttempts = 0;
  call();
}
function on_uid() {
   uuid.innerHTML = "";
   if (dc) {
       // send uid for calibr session
       dc.send("userId "+uuid.value);

   }
}
function on_hide()
{
    document.getElementById('video').style.display = hide.checked ? 'none' : 'block';
   
}
function make_dset(dset_type,dset_mode,dset_name)
{
 
 if (dc != null /*&& dset_nm.value != ""*/) {
     dset.style.display = 'none';
     dset_stop.style.display = 'inline-block'; 
     dc.send(dset_type + dset_name);
     //dset_nm.value = ""; // clear
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
  
  make_dset("dset ",1,dset_nm.value);
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
function on_dset_stop()
{
 if (is_dataset != 0) {
     dset.style.display      = 'inline-block' ;
     dset_stop.style.display = 'none';
     is_dataset = 0; 
     if (dc != null) {
         dc.send("dset-stop");
     }
     exitFullScreen();
 }
}
function on_dset_cancel() {
  if (is_dataset != 0) {
     if (dc != null) {
      dc.send("dsetcancel");
     }
     is_dataset = 0;
     exitFullScreen();
  }
}
function calculate() {

}

function on_chequer() {
    
    make_dset("chequer ",2,dset_nm.value);
}
function next_dset_item() {
    if (is_dataset == 1) {
        calc_by_photo();
    } else if (is_dataset == 2) {
               dist_by_photo();
           }
}

function onPause(e) {
var ev = e;
 dataChannelLog.textContent = 'press pause:\n' + dataChannelLog.textContent;
 lmedia.play();
 lmedia.addEventListener("timeupdate", function() {
    
 }, false);
 setTimeout(function() {
        next_dset_item();
    }, mesure_tout);
 
 return true;
}
function onPlay(e) {
var ev = e;
dataChannelLog.textContent = 'press play:\n' + dataChannelLog.textContent;
}
function start() {
    document.getElementById('start').style.display = 'none';
    uuid.onchange = on_uid;
    lmedia = document.getElementById('video');
    lmedia.addEventListener("pause", onPause, false);
    lmedia.addEventListener("play", onPlay, false);
    
    
    is_mobile = navigator.userAgent.indexOf('Mobile') != -1
    var constraints = {
        audio: document.getElementById('use-audio').checked,
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
                      document.getElementById('get-photo').style.display = 'inline-block';
                      
                
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
              document.getElementById('call').style.display = 'inline-block';
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
    document.getElementById('hangup').style.display = 'none';
    document.getElementById('call').style.display = 'none';
    photo.style.display = 'none';
    calc.style.display = 'none';
    if (localStream != null) {
        pc.getSenders().forEach(function(sender) {
            sender.track.stop();
        });
    }
    closeConnection(pc);
    // close audio / video
    

}
