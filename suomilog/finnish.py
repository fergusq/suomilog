from voikko import libvoikko as lv
from . import patternparser as pp

voikko = lv.Voikko("fi-x-morpho")

def tokenize(text):
	tokens = []
	for token in voikko.tokens(text):
		if token.tokenType == lv.Token.WHITESPACE:
			continue
		baseforms = set()
		bits = set()
		for word in voikko.analyze(token.tokenText):
			if "BASEFORM" in word:
				bf, bs = baseformAndBits(word)
				baseforms.add(bf)
				bits |= bs
		tokens.append(pp.Token(token.tokenText, baseforms, bits))
	return tokens

def baseformAndBits(word):
	bits = set()
	addBits(word, bits, "NUMBER", {"singular": "yksikkö", "plural": "monikko"})
	addBits(word, bits, "SIJAMUOTO")
	return word["BASEFORM"], bits

def addBits(word, bits, name, table=None):
	if name in word:
		if table:
			if word[name] in table:
				bits.add(table[word[name]])
		else:
			bits.add(word[name])
