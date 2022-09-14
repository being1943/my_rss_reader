import unittest


class MyTestCase(unittest.TestCase):
    def test_something(self):
        a = []
        print(a[:2])
        print(len(a))
        for r in a[:2]:
            print(r)


if __name__ == '__main__':
    unittest.main()
