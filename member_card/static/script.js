// python-social-auth related bits:
// First grabbing any auth "disconnect" buttons we have hanging about
// (at the time of this comment's writing, google-oauth2 is the only implicated auth method)
var disconnectAuthButtons = document.getElementsByClassName("disconnect-auth-btn");
var disconnectAuthFunc = function(event) {
  event.preventDefault()
  $(event.target).closest('form').submit();
};

Array.from(disconnectAuthButtons).forEach(function(element) {
  element.addEventListener('click', disconnectAuthFunc);
});
var toggleQrCodeBtn = document.getElementById("toggle-qr-code-btn");
if (toggleQrCodeBtn) {
  toggleQrCodeBtn.addEventListener("click", function () {
    var qrCode = document.getElementById("card-qr-code");
    if (qrCode.style.display === "none") {
      qrCode.style.display = "block";
    } else {
      qrCode.style.display = "none";
    }
  });
}
// document.getElementsByClassName("disconnect-form").addEventListener("click", function (event) {
//   event.preventDefault();
//   $(event.target).closest('form').submit();
// });
var saveScreenshotBtn = document.getElementById("save-as-screenshot-btn");
if (saveScreenshotBtn) {
  saveScreenshotBtn.addEventListener("click", function () {
    html2canvas(document.querySelector('#save-as-screenshot-window'),
      {
        scale: 3,
        backgroundColor: null,
        onclone: function (clonedDoc) {
          clonedDoc.getElementById('card-qr-code').style.display = 'block';
        }
      }).then(function (canvas) {
        saveAs(canvas.toDataURL(), 'lv-members-card.png');
      });
  });
}


function saveAs(uri, filename) {
  var link = document.createElement('a');
  if (typeof link.download === 'string') {
    link.href = uri;
    link.download = filename;

    //Firefox requires the link to be in the body
    document.body.appendChild(link);

    //simulate click
    link.click();

    //remove the link when done
    document.body.removeChild(link);

  } else {
    window.open(uri);
  }
}
