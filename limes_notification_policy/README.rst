Limes notification policy
=========================

This app replaces the forum-notifications-config Tutor build plugin on the
client's release/verawood.1 platform fork. Keep the app label, database table
name and migration names unchanged when rebasing onto later upstream releases.
Never copy these migrations into the upstream notifications app or fake/unapply
them on an existing installation.

Behavior
--------

Email defaults are enabled/Immediately for the same 14 notification types as the
former plugin; subsequent user choices remain effective. Ordinary discussion and
question posts create web notifications without email. Authorized notify-all
posts broadcast through the upstream recipient/access/preference filters.
Replies and nested comments on those threads use the same course audience;
unchecked threads retain upstream author/follower notification behavior. The
current content author is excluded by the upstream sender. The separate
frontend-app-discussions change controls whether the checkbox starts checked.

Migration compatibility
-----------------------

0001_immediate_email_defaults and 0002_broadcastthread are copied verbatim from
the former plugin. Django skips either migration if already recorded. 0002
backfills only retained explicit notify-all notification evidence. Historical
threads with no such evidence keep their normal follower audience.

Before rollout, build the client fork image and remove the old Tutor plugin from
both the enabled plugin list and the server's plugins directory. In the new
image, check the migration plan and model state before stopping LMS/CMS and their
workers. Run LMS and CMS migrations, then migrate --check, before restart.
The limes-tutor Ansible deployment implements that sequence and stops on error.
Back up the database using the normal release procedure before deployment.

On every upstream update, run the isolated regression suite and the normal LMS
integration tests; inspect upstream changes to notification grouping, recipient
selection, email batching, subscription pagination, and thread/reply creation.
Do not remove the compatibility app or renumber its migrations. Add a new
migration for future schema changes. The platform caller consumes follower
pages until an empty result because the Verawood forum dependency reports an
incorrect num_pages; it no longer modifies installed forum package files.

Tests
-----

With Django 5.2 installed::

    python limes_notification_policy/tests/regression.py

The isolated suite executes actual platform function bodies with mocked service
boundaries and real Django migrations against an SQLite upstream-schema fixture.
It covers batches, opt-outs, checked/unchecked threads, replies, pagination and
migration upgrade/reapplication. It does not replace MySQL-backed LMS tests or
staging delivery verification. No outgoing email is sent by this suite.
