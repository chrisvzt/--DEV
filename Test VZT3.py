import random
import time

guess = int(input("What is your guess?: "))
time.get_clock_info
correct_number = random.randint(1,100)
guess_count = 1

while guess != correct_number:
    guess_count += 1
    if guess < correct_number:
        guess = int(input("No the number is higher, guess again: "))
    else:
        guess = int(input("No the number is lower, guess again: "))

print (f'Congrats! The right answer was {correct_number}. It took you {guess_count} guesses. ')


