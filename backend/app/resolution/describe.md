For normalize_name() function:

i will create a fucntion 
def normalize_name(name: str) -> str:
    if name:
        name = name.casefold().strip() //Convert to lowercase and trim leading/trailing whitespace
    
    i would use the removeprefix() method to remove the honorifics

    for the special characters removal i will use: 
    import re
    if not name.isalnum():
        then use re.sub(r'[^a-zA-Z0-9\s]', '', name)

        for the last one ie  Collapse multiple consecutive spaces (e.g. "Rahul   Sharma" ➔ "rahul sharma").

        will use

        name= " ".join(name.split())
 at last return name

For nomalize_phone() functione:
def normalize_phone(phone: str) -> str:
    