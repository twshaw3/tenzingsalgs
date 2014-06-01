$(document).ready(function() {
  $('.toggle_comments').click(function() {
      $("#" + $(this).attr("id") + ".comments").toggle();
      if($(this).html().search("Hide") > 0) {
        $(this).html($(this).html().replace("Hide", "Show"));
      } else {
        $(this).html($(this).html().replace("Show", "Hide"));
      }
  });
});
