from . import parser

cases = [
"+nom",
"+gen",
"+par",
"+ess",
"+abe",
"+tra",
"+ade",
"+abl",
"+all",
"+ine",
"+ela",
"+ill",
]

posses = [
    "+poss1sg",
    "+poss2sg",
    "+poss1pl",
    "+poss2pl",
    "+poss3"
]

while True:
    term = input(">> ")
    res = []
    tags = []
    for poss in posses + [""]:
        for case in cases:
            for plurality in "+sg", "+pl":
                tags.append((case, plurality, poss))
        for case in ("+ins", "+com"):
            tags.append((case, "+pl", poss))
    for case, plurality, poss in tags:
        for x in parser.reinflect(term, case, plurality, poss):
            if x not in res:
                res.append(x)
            
    print(res)