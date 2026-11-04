DIVINE EGG AI TRACKER PRO - ចាប់ផ្ដើមដំឡើង

1) បង្កើត GitHub repository ថ្មី ឈ្មោះ Divine-Egg-AI-Tracker-Pro
2) Upload main.py, requirements.txt, render.yaml, .gitignore និង README_KM.txt
3) Render > New > Blueprint (ឬ Web Service) > ភ្ជាប់ GitHub repository
4) បញ្ចូល TELEGRAM_BOT_TOKEN ជា Environment Variable នៅ Render។ កុំដាក់ Token ក្នុង GitHub ឬផ្ញើក្នុង Chat។
5) កំណត់ DASHBOARD_KEY ជាពាក្យសម្ងាត់វែង និងសម្ងាត់។ DATABASE_PATH ត្រូវជា /var/data/divine_egg.db ប្រសិនបើមាន Persistent Disk។
6) Deploy ហើយបើក https://YOUR-RENDER-URL/health ដើម្បីពិនិត្យ។
7) បើក Website URL ដើម្បីប្រើ Dashboard។ បញ្ចូល DASHBOARD_KEY ពេល Save record។
8) Telegram: /start, /record MAP | EGG | note, /stats, /recent

ចំណាំសំខាន់:
- Bot token ត្រូវបង្កើតថ្មីតាម @BotFather ប្រសិនបើ token ចាស់ធ្លាប់បង្ហោះជាសាធារណៈ។
- មិនមានការភ្ជាប់ live Roblox/game spawn API ក្នុងកញ្ចប់នេះទេ។ ការវិភាគគឺផ្អែកលើកំណត់ត្រាដែលបានបញ្ចូល។
- Persistent Disk របស់ Render ជាទូទៅត្រូវការគម្រោងបង់ប្រាក់; ពិនិត្យលក្ខខណ្ឌ Render មុន Deploy។ បើគ្មាន disk ទិន្នន័យ SQLite អាចបាត់ពេល instance ត្រូវបានជំនួស។
