import random


class RandomUnique:
    instance = None
    @staticmethod
    def singleton():
        if RandomUnique.instance is None:
            RandomUnique.instance = RandomUnique()
        return RandomUnique.instance
    def __init__(self):
        self.nums = set()

    def random(self):
        while True:
            num = random.random()
            if num not in self.nums:
                self.nums.add(num)
                return num