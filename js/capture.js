(function() {
  var width = 640;    // We will scale the photo width to this
  var height = 0;     // This will be computed based on the input stream

  // |streaming| indicates whether or not we're currently streaming
  // video from the camera. Obviously, we start at false.

  var cmd = 'calibr';
  var counter = 1;

  var streaming = false;

  var captureDevice = null;

  var video = null;
  var canvas = null;
  var photo = null;
  var startbutton = null;
  var layer = null;
  var calibr = null;
  var downloadbutton = null;

  function startup() {
    video = document.getElementById('video');
    canvas = document.getElementById('canvas');
    photo = document.getElementById('photo');
    startbutton = document.getElementById('startbutton');
    layer = document.getElementById('layer');
    calibr = document.getElementById('calibr');
    downloadbutton = document.getElementById('download');

    navigator.getMedia = ( navigator.getUserMedia ||
                           navigator.webkitGetUserMedia ||
                           navigator.mozGetUserMedia ||
                           navigator.msGetUserMedia);

    navigator.getMedia(
      {
        video: { facingMode: { exact: "environment" } },
        audio: false
      },
      function(stream) {
        if (navigator.mozGetUserMedia) {
          video.mozSrcObject = stream;
        } else {
          var vendorURL = window.URL || window.webkitURL;
          try {
            video.srcObject = stream;
          } catch (err) {
            video.src = vendorURL.createObjectURL(stream);
            return;
          }
        }
        video.play();
        try {
          videoDevice = stream.getVideoTracks()[0];
          // Check if this device supports a picture mode...
          captureDevice = new ImageCapture(videoDevice);
          //document.getElementById('get-photo').style.display = 'inline-block';
        } catch (err) {
          console.log('Cant get ImageCapture:'+err);
        }
      },
      function(err) {
        console.log("An error occured! " + err);
      }
    );

    video.addEventListener('canplay', function(ev){
      if (!streaming) {
        height = video.videoHeight / (video.videoWidth/width);

        // Firefox currently has a bug where the height can't be read from
        // the video, so we will make assumptions if this happens.

        if (isNaN(height)) {
          height = width / (4/3);
        }

        video.setAttribute('width', width);
        video.setAttribute('height', height);
        canvas.setAttribute('width', width);
        canvas.setAttribute('height', height);
        streaming = true;
        if (cmd === 'calibr') {
          calibr.style.display = 'block';
          setUpCalibr();
        } else {
          layer.style.display = 'block';
        }
      }
    }, false);

    startbutton.addEventListener('click', function(ev){
      takepicture();
      ev.preventDefault();
    }, false);

    downloadbutton.addEventListener('click', function(ev){
      downloadPictures();
      ev.preventDefault();
    }, false);

    clearphoto();
  }

  function setUpCalibr() {
    if (cmd !== 'calibr') {
      calibr.style.display = 'none';
      return;
    }
    var value = counter % 5;
    switch (value) {
      case 1:
        calibr.style.left = '160px';
        calibr.style.top = '45px';
        break;
      case 2:
        calibr.style.left = '275px';
        calibr.style.top = '150px';
        break;
      case 3:
        calibr.style.left = '160px';
        calibr.style.top = '255px';
        break;
      case 4:
        calibr.style.left = '45px';
        calibr.style.top = '150px';
        break;
      case 5:
        calibr.style.left = '160px';
        calibr.style.top = '150px';
        break;
      default:
        console.log("Sorry, we are out of " + value + ".");
    }
  }

  function clearphoto() {
    var context = canvas.getContext('2d');
    context.fillStyle = "#AAA";
    context.fillRect(0, 0, canvas.width, canvas.height);

    var data = canvas.toDataURL('image/png');
    photo.setAttribute('src', data);
  }

  var pictures = [];

  function downloadPictures() {
    pictures.forEach(function(data, i) {
      var link = document.createElement("a");
      link.download = i+'.png';
      link.href = data;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      delete link;
    })
    pictures = [];
  }

  function takepicture() {
    var context = canvas.getContext('2d');
    if (width && height) {
      canvas.width = width;
      canvas.height = height;
      context.drawImage(video, 0, 0, width, height);

      var data = canvas.toDataURL('image/png');
      pictures.push(data);
      photo.setAttribute('src', data);
    } else {
      clearphoto();
    }
  }

  // ---------
  // send photo by POST
  function post_photo() {
    getPhotoForPost =  function (blob) {
      if (blob) {
        sendBlobByPost(blob);
      } else console.log('Cant get photo\n');
    }
    if (captureDevice != null) {
      console.log('Try get photo for post\n');
      captureDevice.takePhoto().then(getPhotoForPost).catch(catchPhoto);
    }
  }

  function catchPhoto(err) {
    //photo.src = "";
    console.log('Cant get photo:'+err);
  }

  function sendBlobByPost(blob) {
    var xhr = new XMLHttpRequest();
    if (cmd === 'calibr') {
      xhr.open("POST", '/mesure?uid=1&dsetnm=first&cmd=calibr', true);
    } else {
      xhr.open("POST", '/chequer?uid=1&dsetnm=first&cmd=calc', true);
    }

    xhr.onreadystatechange = function() {
        if (this.readyState != 4) return;
        console.log('POST '+this.responseText);
        if (cmd = 'calibr') {
          setUpCalibr()
        }
        counter += 1;
        if (counter === 10) {
          counter = 1;
          getMesureResult();
        }
    };
    xhr.upload.onprogress = function(e) {
      if (e.lengthComputable) {

        console.log('Send .. '+ ((e.loaded / e.total) * 100) );
      }
    };
    console.log('Send photo\n');
    var formData = new FormData();
    formData.append('blob', blob);
    xhr.send(formData);
  }

  function getMesureResult() {
    // get result
    var xhr1 = new XMLHttpRequest();
    xhr1.responseType = 'json';
    xhr1.open("GET", '/result?uid=1&dsetnm=first&cmd=result', true);
    xhr1.onload = function(e) {
      if (this.status == 200) {
        var resp = this.response;
        if ((resp.json.status === true) && (cmd === 'calibr')) {
          cmd = 'calc'
          layer.style.display = 'block';
          setUpCalibr();
        }
        console.log('get response '+JSON.stringify(resp));
      }
    };
    xhr1.send();
  }
  // ---------


  window.addEventListener('load', startup, false);
})();
