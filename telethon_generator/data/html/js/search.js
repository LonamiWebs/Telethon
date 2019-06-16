root = document.getElementById("main_div");
root.innerHTML = `
<!-- You can append '?q=query' to the URL to default to a search -->
<input id="searchBox" type="text" onkeyup="updateSearch(event)"
       placeholder="Search for requests and types…" />

<div id="searchDiv">
    <div id="exactMatch" style="display:none;">
        <b>Exact match:</b>
        <ul id="exactList" class="together">
        </ul>
    </div>

    <details id="methods" open><summary class="title">Methods (<span id="methodsCount">0</span>)</summary>
        <ul id="methodsList" class="together">
        </ul>
    </details>

    <details id="types" open><summary class="title">Types (<span id="typesCount">0</span>)</summary>
        <ul id="typesList" class="together">
        </ul>
    </details>

    <details id="constructors"><summary class="title">Constructors (<span id="constructorsCount">0</span>)</summary>
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
methodsDetails = document.getElementById("methods");
methodsList = document.getElementById("methodsList");
methodsCount = document.getElementById("methodsCount");

typesDetails = document.getElementById("types");
typesList = document.getElementById("typesList");
typesCount = document.getElementById("typesCount");

constructorsDetails = document.getElementById("constructors");
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

// Assumes haystack has no whitespace and both are lowercase.
//
// Returns the penalty for finding the needle in the haystack
// or -1 if the needle wasn't found at all.
function find(haystack, needle) {
    if (haystack.indexOf(needle) != -1) {
        return 0;
    }
    var hi = 0;
    var ni = 0;
    var penalty = 0;
    var started = false;
    while (true) {
        while (needle[ni] < 'a' || needle[ni] > 'z') {
            ++ni;
            if (ni == needle.length) {
                return penalty;
            }
        }
        while (haystack[hi] != needle[ni]) {
            ++hi;
            if (started) {
                ++penalty;
            }
            if (hi == haystack.length) {
                return -1;
            }
        }
        ++hi;
        ++ni;
        started = true;
        if (ni == needle.length) {
            return penalty;
        }
        if (hi == haystack.length) {
            return -1;
        }
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
        var penalty = find(original[i].toLowerCase(), query);
        if (penalty > -1 && penalty < original[i].length / 3) {
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

function updateSearch(event) {
    var query = searchBox.value.toLowerCase();
    if (!query) {
        contentDiv.style.display = "";
        searchDiv.style.display = "none";
        return;
    }

    contentDiv.style.display = "none";
    searchDiv.style.display = "";

    var foundRequests = getSearchArray(requests, requestsu, query);
    var foundTypes = getSearchArray(types, typesu, query);
    var foundConstructors = getSearchArray(constructors, constructorsu, query);

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

    if (event && event.keyCode == 13) {
        if (destination.length != 0) {
            window.location = destinationu[0];
        } else if (methodsDetails.open && foundRequests[1].length) {
            window.location = foundRequests[1][0];
        } else if (typesDetails.open && foundTypes[1].length) {
            window.location = foundTypes[1][0];
        } else if (constructorsDetails.open && foundConstructors[1].length) {
            window.location = foundConstructors[1][0];
        }
        return;
    }

    buildList(methodsCount, methodsList, foundRequests);
    buildList(typesCount, typesList, foundTypes);
    buildList(constructorsCount, constructorsList, foundConstructors);

    // Now look for exact matches
    if (destination.length == 0) {
        exactMatch.style.display = "none";
    } else {
        exactMatch.style.display = "";
        buildList(null, exactList, [destination, destinationu]);
        return destinationu[0];
    }
}

function getQuery(name) {
    var query = window.location.search.substring(1);
    var vars = query.split("&");
    for (var i = 0; i != vars.length; ++i) {
        var pair = vars[i].split("=");
        if (pair[0] == name)
            return decodeURI(pair[1]);
    }
}

document.onkeydown = function (e) {
    if (e.key == '/' || e.key == 's' || e.key == 'S') {
        if (document.activeElement != searchBox) {
            searchBox.focus();
            return false;
        }
    } else if (e.key == '?') {
        alert('Pressing any of: /sS\nWill focus the search bar\n\n' +
              'Pressing: enter\nWill navigate to the first match')
    }
}

var query = getQuery('q');
if (query) {
    searchBox.value = query;
}

var exactUrl = updateSearch();
var redirect = getQuery('redirect');
if (exactUrl && redirect != 'no') {
    window.location = exactUrl;
}
