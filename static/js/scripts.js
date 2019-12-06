function formatAsCurrency(){
    const formatter = new Intl.NumberFormat('pl-PL', {
        style: 'currency',
        currency: 'PLN',
        minimumFractionDigits: 2
    });

    var currencyCells = document.getElementsByClassName("currency");
    var convertedContent;
    var link;

    for (var i = 0; i < currencyCells.length; i++ ) {
        link = currencyCells[i].querySelector('a');
        if (link) {
            convertedContent = formatter.format(Number(link.innerText));
            link.innerText = convertedContent
        } else {
            if (currencyCells[i]) {
                convertedContent = formatter.format(Number(currencyCells[i].innerText));
                currencyCells[i].innerText = convertedContent;
            }
        }
    }
}

function highlightMenuItem(){
    var breadcrumb = document.querySelector("ol.breadcrumb");
    var breadcrumbSecond = breadcrumb.children[1];
    var currentPageName = breadcrumbSecond.innerText;

    var linkItems = document.querySelectorAll(".nav-item");
    linkItems.forEach(function (element) {
        if (currentPageName.trim() === (element.firstElementChild.innerText).trim()) {
            element.firstElementChild.className = "nav-link active"
        }
    })
}

$(function(){
     try {
        highlightMenuItem();
    } catch(TypeError) {
        console.error(TypeError)
    }
    try {
        formatAsCurrency();
    } catch(TypeError) {
        console.error(TypeError)
    }
});