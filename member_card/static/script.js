// python-social-auth related bits:
// First grabbing any auth "disconnect" buttons we have hanging about
// (at the time of this comment's writing, google-oauth2 is the only implicated auth method)
const disconnectAuthButtons = document.getElementsByClassName('disconnect-auth-btn')
const disconnectAuthFunc = function (event) {
  event.preventDefault()
  event.target.closest('form').submit()
}

Array.from(disconnectAuthButtons).forEach(function (element) {
  element.addEventListener('click', disconnectAuthFunc)
})

const qrCode = document.getElementById('card-qr-code')
if (qrCode) {
  qrCode.style.display = 'none'
}
const toggleQrCodeBtn = document.getElementById('toggle-qr-code-btn')
if (toggleQrCodeBtn && qrCode) {
  toggleQrCodeBtn.addEventListener('click', function () {
    if (qrCode.style.display === 'none') {
      qrCode.style.display = 'block'
    } else {
      qrCode.style.display = 'none'
    }
  })
}
// document.getElementsByClassName("disconnect-form").addEventListener("click", function (event) {
//   event.preventDefault();
//   $(event.target).closest('form').submit();
// });
const saveScreenshotBtn = document.getElementById('save-as-screenshot-btn')
if (saveScreenshotBtn) {
  saveScreenshotBtn.addEventListener('click', function () {
    html2canvas(document.querySelector('#save-as-screenshot-window'),
      {
        scale: 3,
        backgroundColor: null,
        onclone: function (clonedDoc) {
          clonedDoc.getElementById('card-qr-code').style.display = 'block'
        }
      }).then(function (canvas) {
        saveAs(canvas.toDataURL(), 'lv-members-card.png')
      })
  })
}

function saveAs(uri, filename) {
  const link = document.createElement('a')
  if (typeof link.download === 'string') {
    link.href = uri
    link.download = filename

    // Firefox requires the link to be in the body
    document.body.appendChild(link)

    // simulate click
    link.click()

    // remove the link when done
    document.body.removeChild(link)
  } else {
    window.open(uri)
  }
}

// Email distribution form things:
function sendFormErrorToast(msg, timeout = 5000) {
  var formToastContainer = document.getElementById('toastSnackbar');
  var data = { message: msg, timeout: timeout };
  formToastContainer.MaterialSnackbar.showSnackbar(data);
  // Re-enable the form if we encounter an error so folks can resubmit
  var emailSubmitBtn = document.getElementById("emailDistributionSubmitBtn");
  var emailProgressBar = document.getElementById("emailDistributionProgressBar");
  if (emailSubmitBtn && emailProgressBar) {
    emailSubmitBtn.disabled = false;
    emailProgressBar.style.display = "none";
  }
}

function gpaySaveSuccessHandler() {
  sendFormErrorToast('Membership card saved as GPay Pass! :D')
}

function gpaySaveFailureHandler(err) {
  sendFormErrorToast('GPay Pass save error: ' + err.errorCode + ': ' + err.errorMessage);
}

function onCaptchaExpired() {
  sendFormErrorToast('Form (captcha) data has expired. Please try submitting again in a moment.')
}

function onCaptchaError() {
  sendFormErrorToast('Form (captcha) encountered an error. Please try submitting again in a moment.')
}

function validate(event) {
  event.preventDefault();
  var form = event.target.closest('form');
  var formElements = form.elements;
  for (var i = 0, formElement; formElement = formElements[i++];) {
    if (!formElement.classList.contains("mdl-textfield__input")) {
      // console.debug("skipping formElement " + formElement.id + ", is is not one of our mdl-textfield__inputs...")
      continue
    }
    if (!formElement.value || formElement.parentElement.classList.contains("is-invalid")) {
      var errorMsg = 'Please enter a valid value for ' + formElement.name + ' before submitting.';
      elementErrorMsgSpans = formElement.parentNode.getElementsByTagName('span')
      if (elementErrorMsgSpans.length) {
        errorMsg = elementErrorMsgSpans[0].textContent;
      }
      sendFormErrorToast(errorMsg)
      return
    }
  }

  document.getElementById("emailDistributionSubmitBtn").disabled = true;
  document.getElementById("emailDistributionProgressBar").style.display = "block";
  grecaptcha.execute();
}

function onSubmit(token) {
  document.getElementById("emailDistributionRequestForm").submit();
}

function distributionFormOnload() {
  var element = document.getElementById('emailDistributionSubmitBtn');
  element.onclick = validate;
}
