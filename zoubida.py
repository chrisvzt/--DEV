# Prompt the user
user_input = input("Please enter a number: ")

try:
    # Try to convert to a numeric type
    # Use int(...) if you only want integers, or float(...) for decimals
    num = int(user_input)
    
    # Now you know 'num' is a valid integer, you can compare:
    if num % 2 == 0:
        print(f"{num} is even.")
    else:
        print(f"{num} is odd.")
    
    # Example of another comparison:
    if num > 0:
        print(f"{num} is positive.")
    elif num < 0:
        print(f"{num} is negative.")
    else:
        print("You entered zero.")
    
except ValueError:
    # This block runs if int(user_input) failed
    print(f"❌ “{user_input}” is not a valid integer. Please enter digits only.")
    
#def double(number):
#    return number * 2