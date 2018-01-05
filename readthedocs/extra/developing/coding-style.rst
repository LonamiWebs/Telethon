============
Coding Style
============


Basically, make it **readable**, while keeping the style similar to the
code of whatever file you're working on.

Also note that not everyone has 4K screens for their primary monitors,
so please try to stick to the 80-columns limit. This makes it easy to
``git diff`` changes from a terminal before committing changes. If the
line has to be long, please don't exceed 120 characters.

For the commit messages, please make them *explanatory*. Not only
they're helpful to troubleshoot when certain issues could have been
introduced, but they're also used to construct the change log once a new
version is ready.

If you don't know enough Python, I strongly recommend reading `Dive Into
Python 3 <http://www.diveintopython3.net/>`__, available online for
free. For instance, remember to do ``if x is None`` or
``if x is not None`` instead ``if x == None``!
