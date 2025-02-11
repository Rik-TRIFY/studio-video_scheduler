import hashlib

def generate_license_key(email):
    secret_code = '0fc081be3aaaa55bec5e2098eb7cc8ec'
    return hashlib.md5(f"{email}{secret_code}".encode()).hexdigest()

# Test s emailom
email = input("Zadajte email: ")
license_key = generate_license_key(email)

print("\nEmail:", email)
print("Licenčný kľúč:", license_key)