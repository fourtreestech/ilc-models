API
===

The models are organised into submodules by domain, documented below. Every
public name is re-exported from the top-level package, so import them from
`ilc_models` directly rather than from a submodule::

    from ilc_models import League, Match, User

.. automodule:: ilc_models

Players
-------

.. automodule:: ilc_models.player
   :members:
   :exclude-members: model_config

Lineups
-------

.. automodule:: ilc_models.lineup
   :members:
   :exclude-members: model_config

Events
------

.. automodule:: ilc_models.event
   :members:
   :exclude-members: model_config

Matches
-------

.. automodule:: ilc_models.match
   :members:
   :exclude-members: model_config

League tables
-------------

.. automodule:: ilc_models.table
   :members:
   :exclude-members: model_config

Leagues
-------

.. automodule:: ilc_models.league
   :members:
   :exclude-members: model_config

Users
-----

.. automodule:: ilc_models.user
   :members:
   :exclude-members: model_config
