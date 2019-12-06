$(function() {
    var allRowsButton = $('#all-items');
    var userRowsButton = $('#user-items');
    var rows = $('tr.dynamic-row');
    var user = $('#user_logged').attr('data-user');

    userRowsButton.on('click', function () {
        rows.each(function (index, element) {
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
        rows.each(function (index, element) {
            $(this).show();
        })
    });
});