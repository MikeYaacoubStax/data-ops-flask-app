# Create a new orphan branch with current content
git checkout --orphan temp
git add -A
git commit -m "Fresh start"
# Delete all branches and replace main with temp
git branch -D main
git branch -m main
# Force push to remote
git push -f origin main