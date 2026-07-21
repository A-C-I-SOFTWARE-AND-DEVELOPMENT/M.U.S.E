from strings import reverse_words

def test_reverse():
    assert reverse_words('hello world') == 'world hello'
    assert reverse_words('a b c') == 'c b a'
    assert reverse_words('one') == 'one'
