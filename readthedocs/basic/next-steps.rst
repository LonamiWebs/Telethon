==========
Next Steps
==========

These basic first steps should have gotten you started with the library.

By now, you should know how to call friendly methods and how to work with
the returned objects, how things work inside event handlers, etc.

Next, we will see a quick reference summary of *all* the methods and
properties that you will need when using the library. If you follow
the links there, you will expand the documentation for the method
and property, with more examples on how to use them.

Therefore, **you can find an example on every method** of the client
to learn how to use it, as well as a description of all the arguments.

After that, we will go in-depth with some other important concepts
that are worth learning and understanding.

From now on, you can keep pressing the "Next" button if you want,
or use the menu on the left, since some pages are quite lengthy.

A note on developing applications
=================================

If you're using the library to make an actual application (and not just
automate things), you should make sure to `comply with the ToS`__:

    […] when logging in as an existing user, apps are supposed to call
    [:tl:`GetTermsOfServiceUpdate`] to check for any updates to the Terms of
    Service; this call should be repeated after ``expires`` seconds have
    elapsed. If an update to the Terms Of Service is available, clients are
    supposed to show a consent popup; if accepted, clients should call
    [:tl:`AcceptTermsOfService`], providing the ``termsOfService id`` JSON
    object; in case of denial, clients are to delete the account using
    [:tl:`DeleteAccount`], providing Decline ToS update as deletion reason.

.. __: https://core.telegram.org/api/config#terms-of-service

However, if you use the library to automate or enhance your Telegram
experience, it's very likely that you are using other applications doing this
check for you (so you wouldn't run the risk of violating the ToS).

The library itself will not automatically perform this check or accept the ToS
because it should require user action (the only exception is during sign-up).
