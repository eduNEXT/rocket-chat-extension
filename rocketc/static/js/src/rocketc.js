/* Javascript for RocketChatXBlock. */
function RocketChatXBlock(runtime, element) {

    var dataState;

    $(function ($) {
        var block = $(element).find('.rocketc_block');
        dataState = block.attr('data-state');
    });

    var  logoutUser= runtime.handlerUrl(element, "logout_user");
    console.log ("Andrey was here");

    $( window ).onbeforeunload(function() {
        
        dataState = JSON.parse(dataState);
        var data = dataState
        $.ajax({
            type: "POST",
            url: logoutUser,
            data: JSON.stringify(data),
        });
    });
}
