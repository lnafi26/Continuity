Issues Listed Here:
## Brand Name
- [] Be sure to fix it - It should not stay with the default name (Threadline)
## Login Page
- [Fixed] Line 92 in index.html, the page should not expect users to provide the username as well, usually the gmail and password should be good enough
- [Fixed] The login page design is horrible... It should be a complete page, instead of just a "half page transparent pop up window" - the "Create an account" feature is still confusing - we shouldn't expect the users to see the small line underneath to see "Account created", they should be taken into a separate page or pop up window when the user requests to create an account, and when they finished creating the account, they are taken back to the login page again to sign in normally
- [Fixed] After you login, log out, your password should not stay in the Login page text field, that is a **Security Concern**

## Main Dashboard Home Page
- [] Something still feels off with the main dashboard page, it should designed so the user right away understand they are expected to integrate their gmail, Google Calendar or Slack (optional for now) as the primary feature for the application, right now it's still unclear what the UI is expecting the user to do
- [] Also, for active projects section, **may need further refinement**, it doesn't show clearly the breakdown for all projects except: 
    - Active Projects
    - Open Action Items
    - Recent Actions
    - Items Connected
- [] Even for the Active Projects Section on the dashboard, it should not do the following:
    - The right arrow button takes you to see more details about the project, which is good, BUT
    - When you click on the three dots within each project panel, currently it's not doing anything, **it needs clear definition what should be done** 

- [] The index.html page is showing placeholder content, sure, but it should be CLEARLY showing the user that they don't have project or any files integrated yet, meaning **it shouldn't be showing the hardcoded fabricated content, which is misleading**

## Database Issue
- In Supabase_queries, 


## User Access
- Work In Progress
    - [] Still different level of access
        - Admin
        - Regular users
        - (Optional / Maybe) Guest


