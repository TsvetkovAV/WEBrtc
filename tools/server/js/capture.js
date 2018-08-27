(function() {
  var width = 1280;    // We will scale the photo width to this
  var height = 0;     // This will be computed based on the input stream

  // |streaming| indicates whether or not we're currently streaming
  // video from the camera. Obviously, we start at false.

  // var cmd = 'calibr';
  var cmd = 'calc';
  var counter = 1;
  var statusText = null;

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
    statusText = document.getElementById('status');

    navigator.getMedia = ( navigator.getUserMedia ||
                           navigator.webkitGetUserMedia ||
                           navigator.mozGetUserMedia ||
                           navigator.msGetUserMedia);
    is_mobile = navigator.userAgent.indexOf('Mobile') != -1
    navigator.getMedia(
      {
        video: { facingMode:is_mobile ? { exact: "environment" } : {} },
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
          height = width / (16/9);
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
      // post_photo();
      post_photo_and_get_result();
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
      case 0:
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

      var a = document.createElement("a");
      document.body.appendChild(a);
      a.style = "display: none";
      var json = JSON.stringify(data),
          blob = new Blob([json], {type: "image/png"}),
          url = window.URL.createObjectURL(blob);
      a.href = url;
      a.download = i+'.png';
      a.click();
      window.URL.revokeObjectURL(a);
      //
      // var link = document.createElement("a");
      // link.download = i+'.png';
      // link.href = data;
      // document.body.appendChild(link);
      // link.click();
      // document.body.removeChild(link);
      delete a;
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
      photo.setAttribute('src', data);
    } else {
      clearphoto();
    }
  }

  function changeUnderPhotoText(text) {
    statusText.innerText = text;
  }

  // ---------
  // send photo by POST and get result
  function post_photo_and_get_result() {
    getPhotoForPost =  function (blob) {
      if (blob) {
        sendBlobByPostAndGetResult(blob);
      } else console.log('Cant get photo\n');
    }
    if (captureDevice != null) {
      console.log('Try get photo for post\n');
      var options = {imageHeight: 720, imageWidth: 1280};
      captureDevice.takePhoto(options)
      .then(getPhotoForPost).catch(catchPhoto);
    }
  }
  function sendBlobByPostAndGetResult(blob) {
    pictures.push(blob);
    var xhr = new XMLHttpRequest();
    xhr.open("POST", '/mesure?uid=1&dsetnm=first&cmd=calc', true);

    xhr.onreadystatechange = function() {
        if (this.readyState != 4) return;
        changeUnderPhotoText(this.response);
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
      var options = {imageHeight: 720, imageWidth: 1280};
      captureDevice.takePhoto(options)
      .then(getPhotoForPost).catch(catchPhoto);
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
      xhr.open("POST", '/mesure?uid=1&dsetnm=first&cmd=calc', true);
    }

    xhr.onreadystatechange = function() {
        if (this.readyState != 4) return;
        changeUnderPhotoText(this.response);
        console.log('POST '+this.responseText);
        if (cmd === 'calibr') {
          setUpCalibr()
        }
        var resp = JSON.parse(this.responseText);
        if (resp.ret == 0) {
          if (resp.status != true ) {
              console.log('Bad photo '+resp.cnt);
          }

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
    xhr1.open("GET", '/result?uid=1&dsetnm=first&cmd=dset-stop', true);
    xhr1.onload = function(e) {
      if (this.status == 200) {
        var resp = this.response;
        if ((resp.status === true) && (cmd === 'calibr')) {
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
