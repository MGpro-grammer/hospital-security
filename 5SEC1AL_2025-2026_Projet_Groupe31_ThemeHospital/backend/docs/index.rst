Documentation developpeur - Hospital Security (back-end)
========================================================

Projet 5SEC1A, groupe 31.

Cette documentation est **extraite du code source**. Elle ne peut pas
diverger de l'implementation : toute modification d'une docstring se
repercute a la generation suivante.

.. contents:: Sommaire
   :depth: 2


Application ``accounts``
------------------------

Identite des utilisateurs, cles cryptographiques, relations
patient-medecin.

Modeles
^^^^^^^

.. automodule:: accounts.models
   :members:

Authentification
^^^^^^^^^^^^^^^^

.. automodule:: accounts.authentication
   :members:

Permissions
^^^^^^^^^^^

.. automodule:: accounts.permissions
   :members:

Limitation de debit
^^^^^^^^^^^^^^^^^^^

.. automodule:: accounts.throttling
   :members:

Serialiseurs
^^^^^^^^^^^^

.. automodule:: accounts.serializers
   :members:

Vues
^^^^

.. automodule:: accounts.views
   :members:


Application ``records``
-----------------------

Dossiers medicaux chiffres de bout en bout, cles de fichier et
manifeste signe.

Modeles
^^^^^^^

.. automodule:: records.models
   :members:

Serialiseurs
^^^^^^^^^^^^

.. automodule:: records.serializers
   :members:

Vues
^^^^

.. automodule:: records.views
   :members:


Configuration
-------------

.. automodule:: config.settings
   :members: