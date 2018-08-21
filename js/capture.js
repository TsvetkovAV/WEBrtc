(function() {
  var width = 640;    // We will scale the photo width to this
  var height = 0;     // This will be computed based on the input stream

  // |streaming| indicates whether or not we're currently streaming
  // video from the camera. Obviously, we start at false.

  var streaming = false;

  var video = null;
  var canvas = null;
  var photo = null;
  var startbutton = null;
  var layer = null;
  var downloadbutton = null;

  function startup() {
    video = document.getElementById('video');
    canvas = document.getElementById('canvas');
    photo = document.getElementById('photo');
    startbutton = document.getElementById('startbutton');
    layer = document.getElementById('layer');
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
            video.src = vendorURL.createObjectURL(stream);
          } catch (err) {
            video.srcObject = stream;
            return;
          }
        }
        video.play();
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
        layer.style.display = 'block';
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

  window.addEventListener('load', startup, false);
})();
