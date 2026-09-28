"""Fix corrupted newlines in employees/forms.py after PowerShell mangled them."""
with open('management_system/employees/forms.py', 'rb') as f:
    content = f.read().decode('utf-8')

# The PowerShell command inserted literal backtick-r-backtick-n sequences
bad = '`r`n'
good = '\n'
fixed = content.replace(bad, good)
if fixed != content:
    with open('management_system/employees/forms.py', 'wb') as f:
        f.write(fixed.encode('utf-8'))
    print(f'Fixed - replaced {content.count(bad)} occurrences')
else:
    print('No bad patterns found')
