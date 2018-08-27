
var img       = document.getElementById("image"),
    output    = document.getElementById("output"),
    scaleUp   = document.getElementById('scaleUp'),
    scaleDown = document.getElementById('scaleDown'),
    setSize   = document.getElementById('setSize'),
    goBack    = document.getElementById('goBack'),
    goMesure  = document.getElementById('goMesure'),
    dataChannelLog = document.getElementById('channelLog');

var pc = null, // webRTC connection
    dc = null;

function scale(px_step) {
    img.style.width = img.width + px_step + "px";
    img.style.height = "auto";
}

function printSize() {
    const card_width = 85.6; // mm
    const card_height = 53.98; // mm
    const circle_d = 98; //146; px
    let px_width = card_width / img.width;
    let px_height = card_height / img.height;

    output.innerHTML = "Image dimensions: " + img.width + "x" + img.height + "; pixel dimensions: " + px_width + "x" + px_height + " mm";


    img.onload = function() {
        scaleUp.style.display = 'none';
        scaleDown.style.display = 'none';
        setSize.style.display = 'none';
        goBack.style.display = 'inline-block';
        goMesure.style.display = 'inline-block';
        //output.innerHTML = "Image dimensions: " + this.naturalWidth + "x" + this.naturalHeight + "circle D=" + px_width * 146 + " mm;";
        output.innerHTML = "Circle's diameter=" + px_width * circle_d + " mm; Pixel size = "+px_width+" mm;";
        this.style.height = "auto";
        this.style.width = this.naturalWidth + "px";
        if (dc != null) {
          dc.send("pixsize "+px_width);
        }
        /*
        setTimeout(function() {  
          img.style.height = "auto";
          img.style.width = img.naturalWidth  + "px";
        }, 500);
        */

    }
    img.src = "img/chequer.png"; //"img/circle_99.png";

}
function back() {
        img.onload = function() {
          scaleUp.style.display = 'inline-block';
          scaleDown.style.display = 'inline-block';
          setSize.style.display = 'inline-block';
          goBack.style.display = 'none';
          goMesure.style.display = 'none';
          output.innerHTML = "";
          dataChannelLog.innerHTML = "";
          this.style.height = "auto";
          this.style.width = 258 + "px";
        

        }
        img.src="img/card.png"; 
        
}
function mesure() {
    img.onload = function() {
          goMesure.style.display = 'none';
          this.style.height = "auto";
          this.style.width = this.naturalWidth + "px";
        

    }
    img.src = "img/circle_99.png";
    
}
function buttonHold(btn, px_step) {
    const ms = 25;
    let t;

    function repeat() {
        scale(px_step);
        t = setTimeout(repeat, ms);
    }

    btn.onmousedown = repeat;

    btn.onmouseup = function() {
        clearTimeout(t);
    }

        btn.onmouseleave = btn.onmouseup;
}

buttonHold(document.getElementById("scaleUp"), 1);
buttonHold(document.getElementById("scaleDown"), -1)

function negotiate(pc) {
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
        //document.getElementById('offer-sdp').textContent = offer.sdp;
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
        //document.getElementById('answer-sdp').textContent = answer.sdp;
        return pc.setRemoteDescription(answer);
    });
}


function makeConnection() {
    var is_ping = false;
    pc = new RTCPeerConnection(); // create new one
    dc = pc.createDataChannel('chat');
    dc.onclose = function() {
        clearInterval(dcInterval);
        dataChannelLog.innerHTML = 'close';
    };
    dc.onopen = function() {
        dataChannelLog.innerHTML = 'open connection';
        
        dcInterval = setInterval(function() {
                var message = 'Ping';
                if (is_ping) {
                    dataChannelLog.innerHTML = '> ' + message;
                    dc.send(message);
                }
                
                
            }, 1000);
    };
    dc.onmessage = function(evt) {
        //dataChannelLog.innerHTML = evt.data;
        if (evt.data.substr(0,6) == "userId") {
            dataChannelLog.innerHTML = "UID: " + evt.data.substr(6) + ' - use this ID on your Smart phone';
        } else if (evt.data.substr(0,4) == "pong") {
            dataChannelLog.innerHTML = evt.data;
        }
    };

    negotiate(pc);

}
makeConnection();
