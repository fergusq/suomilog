Suomilog
########

Suomilog is a toolkit for parsing context-free grammars that have embedded morphological information.
It's intended use is parsing Finnish sentences and it includes a module that can parse and generate inflected Finnish sentences using libvoikko as back-end.

Context-free grammars
---------------------

The ``suomilog`` module is used for parsing context-free grammars.
Suomilog grammars are context-free grammars that have additional morphological information. Below is an example.

::

    .FEATURE ::= .HUMAN{+gen} nimi{$}
    .FEATURE ::= .HUMAN{+gen} ikä{$}

    .HUMAN ::= mies{$}
    .HUMAN ::= nainen{$}
    .HUMAN ::= ihminen{$}
    .HUMAN ::= .ADJECTIVE{$} .HUMAN{$}

    .ADJECTIVE ::= ahkera{$}
    .ADJECTIVE ::= kaunis{$}
    .ADJECTIVE ::= erittäin .ADJECTIVE{$}

In Suomilog grammars nonterminals are marked with a dot and all other symbols are terminals.

Morphological information is written in braces after a symbol.
For example ``kaunis{+gen}`` would match the word ``kauniin``.
A dollar ``$`` means that the morphological information is passed forward.
So ``.HUMAN{+gen}`` for example mathes ``miehen``, ``naisen``, ``ihmisen``, ``ahkeran miehen``, and so on.

The braces can contain multiple form names separated with commas. For example, ``tehdä{+inf3,+gen}`` would match ``tekemisen``.
In code these form names are called "bits".

For example usage, see the ``examples/`` folder.

Finnish morphology
------------------

The ``suomilog.finnish`` module contains tools for Finnish morphological parsing and generation.
It uses pypykko as its back-end.

The function ``suomilog.finnish.tokenize(text)`` is used to tokenize words::

    import suomilog.finnish as f
    f.tokenize("kissa käveli kadulla")
    # outputs:
    [
        Token('kissa', [('kissa', {'', '+sg+nom', ':noun', '«kissa»', 'kissa:noun', 'kissa:', '+sg', '+nom'})]),
        Token('käveli', [('kävellä', {'', '+3sg', '«käveli»', 'kävellä:', ':verb', 'kävellä:verb', '+past'})]),
        Token('kadulla', [('katu', {'', ':noun', 'katu:', '«kadulla»', '+ade', '+sg', 'katu:noun'})])
    ]

The function ``suomilog.finnish.inflect_nominal(word, plural, case)`` is used to inflect nouns, adjectives and numerals::

    import suomilog.finnish as f
    print(f.inflect_nominal("kissa", "+pl", "+par")) # kissoja


