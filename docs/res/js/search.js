root = document.getElementById("main_div");
root.innerHTML = `
<!-- You can append '?q=query' to the URL to default to a search -->
<input id="searchBox" type="text" onkeyup="updateSearch()"
       placeholder="Search for requests and types…" />

<div id="searchDiv">
    <div id="exactMatch" style="display:none;">
        <b>Exact match:</b>
        <ul id="exactList" class="together">
        </ul>
    </div>

    <details open><summary class="title">Methods (<span id="methodsCount">0</span>)</summary>
        <ul id="methodsList" class="together">
        </ul>
    </details>

    <details open><summary class="title">Types (<span id="typesCount">0</span>)</summary>
        <ul id="typesList" class="together">
        </ul>
    </details>

    <details><summary class="title">Constructors (<span id="constructorsCount">0</span>)</summary>
        <ul id="constructorsList" class="together">
        </ul>
    </details>
</div>
<div id="contentDiv">
` + root.innerHTML + "</div>";

// HTML modified, now load documents
contentDiv = document.getElementById("contentDiv");
searchDiv = document.getElementById("searchDiv");
searchBox = document.getElementById("searchBox");

// Search lists
methodsList = document.getElementById("methodsList");
methodsCount = document.getElementById("methodsCount");

typesList = document.getElementById("typesList");
typesCount = document.getElementById("typesCount");

constructorsList = document.getElementById("constructorsList");
constructorsCount = document.getElementById("constructorsCount");

// Exact match
exactMatch = document.getElementById("exactMatch");
exactList = document.getElementById("exactList");

try {
    requests = [{request_names}];
    types = [{type_names}];
    constructors = [{constructor_names}];

    requestsu = [{request_urls}];
    typesu = [{type_urls}];
    constructorsu = [{constructor_urls}];
} catch (e) {
    requests = [];
    types = [];
    constructors = [];
    requestsu = [];
    typesu = [];
    constructorsu = [];
}

if (typeof prependPath !== 'undefined') {
    for (var i = 0; i != requestsu.length; ++i) {
        requestsu[i] = prependPath + requestsu[i];
    }
    for (var i = 0; i != typesu.length; ++i) {
        typesu[i] = prependPath + typesu[i];
    }
    for (var i = 0; i != constructorsu.length; ++i) {
        constructorsu[i] = prependPath + constructorsu[i];
    }
}

// Given two input arrays "original" and "original urls" and a query,
// return a pair of arrays with matching "query" elements from "original".
//
// TODO Perhaps return an array of pairs instead a pair of arrays (for cache).
function getSearchArray(original, originalu, query) {
    var destination = [];
    var destinationu = [];

    for (var i = 0; i < original.length; ++i) {
        if (original[i].toLowerCase().indexOf(query) != -1) {
            destination.push(original[i]);
            destinationu.push(originalu[i]);
        }
    }

    return [destination, destinationu];
}

// Modify "countSpan" and "resultList" accordingly based on the elements
// given as [[elements], [element urls]] (both with the same length)
function buildList(countSpan, resultList, foundElements) {
    var result = "";
    for (var i = 0; i < foundElements[0].length; ++i) {
        result += '<li>';
        result += '<a href="' + foundElements[1][i] + '">';
        result += foundElements[0][i];
        result += '</a></li>';
    }

    if (countSpan) {
        countSpan.innerHTML = "" + foundElements[0].length;
    }
    resultList.innerHTML = result;
}

function updateSearch() {
    if (searchBox.value) {
        contentDiv.style.display = "none";
        searchDiv.style.display = "";

        var query = searchBox.value.toLowerCase();

        var foundRequests = getSearchArray(requests, requestsu, query);
        var foundTypes = getSearchArray(types, typesu, query);
        var foundConstructors = getSearchArray(
            constructors, constructorsu, query
        );

        buildList(methodsCount, methodsList, foundRequests);
        buildList(typesCount, typesList, foundTypes);
        buildList(constructorsCount, constructorsList, foundConstructors);

        // Now look for exact matches
        var original = requests.concat(constructors);
        var originalu = requestsu.concat(constructorsu);
        var destination = [];
        var destinationu = [];

        for (var i = 0; i < original.length; ++i) {
            if (original[i].toLowerCase().replace("request", "") == query) {
                destination.push(original[i]);
                destinationu.push(originalu[i]);
            }
        }

        if (destination.length == 0) {
            exactMatch.style.display = "none";
        } else {
            exactMatch.style.display = "";
            buildList(null, exactList, [destination, destinationu]);
        }
    } else {
        contentDiv.style.display = "";
        searchDiv.style.display = "none";
    }
}

function getQuery(name) {
    var query = window.location.search.substring(1);
    var vars = query.split("&");
    for (var i = 0; i != vars.length; ++i) {
        var pair = vars[i].split("=");
        if (pair[0] == name)
            return pair[1];
    }
}

var query = getQuery('q');
if (query) {
    searchBox.value = query;
}

updateSearch();
