function filterCheckboxForm(sourceId, targetId) {
    var selectSource = document.querySelector("#" + sourceId);
    var toFilter = document.querySelectorAll("." + targetId);

    selectSource.addEventListener("click", function (event) {
        var selectedValue = selectSource.options[selectSource.selectedIndex].value;
        toFilter.forEach(function (element) {
            if (selectedValue !== element.dataset.account_id) {
                element.checked = false;
                element.querySelector("input").checked = false;
                element.style.display = 'none';
            } else {
                element.style.display = 'block';
                element.querySelector("input").checked = true;
            }
        });
    });
}

function filterDropdownList(sourceId, targetId) {
    var selectSource = document.querySelector("#" + sourceId);
    var toFilter = document.querySelector("#" + targetId).querySelectorAll("option");
    selectSource.addEventListener("click", function (event) {
        var selectedValue = selectSource.options[selectSource.selectedIndex].value;
        toFilter.forEach(function (element) {
            if (selectedValue !== element.dataset.account_id) {
                element.style.display = 'none';
            } else {
                element.style.display = 'block';
            }
        });
    });
}


$(function(){
    try {
        filterCheckboxForm('id_account', 'hiding');
        filterDropdownList('id_account', 'id_campaign_group');
    } catch(TypeError) {
        console.error(TypeError)
    }
});