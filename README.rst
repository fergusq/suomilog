Suomilog
########

Suomilog is a toolkit for parsing context-free grammars that have embedded morphological information.
It's intended use is parsing Finnish sentences and it includes a module that can parse and generate inflected Finnish sentences using libvoikko as back-end.

Context-free grammars
---------------------

The ``suomilog.patternparser`` module is used for parsing context-free grammars.
Suomilog grammars are context-free grammars that have additional morphological information. Below is an example.

::

    .FEATURE ::= .HUMAN{omanto} nimi{$}
    .FEATURE ::= .HUMAN{omanto} ikä{$}

    .HUMAN ::= mies{$}
    .HUMAN ::= nainen{$}
    .HUMAN ::= ihminen{$}
    .HUMAN ::= .ADJECTIVE{$} .HUMAN{$}

    .ADJECTIVE ::= ahkera{$}
    .ADJECTIVE ::= kaunis{$}
    .ADJECTIVE ::= erittäin .ADJECTIVE{$}

In Suomilog grammars nonterminals are marked with a dot and all other symbols are terminals.

Morphological information is written in braces after a symbol.
For example ``kaunis{omanto}`` would match the word ``kauniin``.
A dollar ``$`` means that the morphological information is passed forward.
So ``.HUMAN{omanto}`` for example mathes ``miehen``, ``naisen``, ``ihmisen``, ``ahkeran miehen``, and so on.

The braces can contain multiple form names separated with commas. For example, ``tehdä{-minen,omanto}`` would match ``tekemisen``.
In code these form names are called "bits".

For example usage, see the ``examples/`` folder.

Finnish morphology
------------------

The ``suomilog.finnish`` module contains tools for Finnish morphological parsing and generation.
It uses libvoikko as its back-end.

Supported forms are at least (there can be others as some are directly from Voikko's format and not all supported by Voikko are listed here):

============= ================ =======
Bit name      Description      Example
============= ================ =======
nimento       nominative case  kissa
omanto        genitive case    kissan
osanto        partitive case   kissaa
olento        essive case      kissana
tulento       translative case kissaksi
ulkotulento   allative case    kissalle
ulkoolento    adessive case    kissalla
ulkoeronto    ablative case    kissalta
sisatulento   illative case    kissaan
sisaolento    inessive case    kissassa
sisaeronto    elative case     kissasta
vajanto       abessive case    kissatta
keinonto      instructive case kissoin
seuranto      comiitative case kissoineni
kerrontosti   adverb           kauniisti
yksikkö       singular         kissa
monikko       plural           kissat
nimisana      noun             kissa
laatusana     adjective        kaunis
teonsana      verb             nähdä
lukusana      numeral          kaksi
-minen        MINEN-infinitive näkeminen
-ma           MA-infinitive    näkemä
-e            E-infinitive     nähden
-a            A-infinitive     nähdä
imperatiivi   imperative       näe
indikatiivi   indicative       näet
konditionaali conditional      näkisit
potentiaali   potential        nähnet
1             first person     näen
2             second person    näet
3             third person     näkee
============= ================ ======

The function ``suomilog.finnish.tokenize(text)`` is used to tokenize words::

    import suomilog.finnish as f
    print(f.tokenize("kissa käveli kadulla"))
    # [Token('kissa', [('kissa', {'nimento', 'yksikkö', 'nimisana'})]), Token('käveli', [('kävellä', {'3', 'teonsana', 'yksikkö', 'indikatiivi'})]), Token('kadulla', [('katu', {'ulkoolento', 'yksikkö', 'nimisana'})])]

The function ``suomilog.finnish.inflect(word, case, plural)`` is used to inflect nouns, adjectives and numerals::

    import suomilog.finnish as f
    print(f.inflect("kissa", "osanto", True)) # kissoja


