$(function() {
    var allRowsButton = $('#all-items');
    var userRowsButton = $('#user-items');
    var divs = $('div.dynamic-div');
    var user = $('#user_logged').attr('data-user');


    divs.each(function (index, element) {
        var userIds = $(this).attr('data-user');
        var users = userIds.slice(0, -1);
        var userList = users.split(',');
        console.log(userList);
        if (!(userList.includes(user))) {
            $(this).hide();
        }
    });

    userRowsButton.on('click', function () {
        divs.each(function (index, element) {
            var userIds = $(this).attr('data-user');
            var users = userIds.slice(0, -1);
            var userList = users.split(',');
            if (userList.includes(user)) {
            } else {
                $(this).hide();
            }
        })
    });

    allRowsButton.on('click', function () {
        divs.each(function (index, element) {
            $(this).show();
        })
    });
});