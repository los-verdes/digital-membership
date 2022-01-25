// $(document).ready(function () {
//   $('.disconnect-form').on('click', 'a.mdl-navigation__link', function (event) {
//     event.preventDefault();
//     $(event.target).closest('form').submit();
//   });
// });

document.getElementsByClassName("disconnect-form").addEventListener("click", function (event) {
  event.preventDefault();
  $(event.target).closest('form').submit();
});

document.getElementById("download").addEventListener("click", function () {
  html2canvas(document.querySelector('#boundary')).then(function (canvas) {
    saveAs(canvas.toDataURL(), 'lv-members-card.png');
  });
});


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
