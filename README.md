# אוצר שיעורי ר' יואל (הגה"ח רבי יואל כהן ע"ה)

אתר סטטי מהיר המאחד אינדקס מטה-דאטה של **9,134 שיעורים, חזרות, התוועדויות, ספרי ר' יואל וחוברות לימוד** בתוך **1,488 סדרות רצופות** מ-13 מקורות — **ללא שמירה מקומית של קובצי שמע, וידאו או PDF** (כל המדיה מוזרמת מהשרתים המקוריים בלבד).

## פרסום חינמי לאינטרנט
1. **GitHub Pages (מומלץ לחינמיות ארוכת-טווח ללא הגבלת תעבורה נוקשה):**
   - הריפו ב-GitHub: `https://github.com/aba-tordoz/OTZAR-REB-YOEL.git`
   - דחיפה מתיקיית הפרויקט:
     ```powershell
     git remote add origin https://github.com/aba-tordoz/OTZAR-REB-YOEL.git
     git push -u origin main
     ```
   - ב-GitHub היכנס ל-**Settings ← Pages ← Source: Deploy from a branch (`main` / `(root)`)** — האתר יעלה לכתובת `https://aba-tordoz.github.io/OTZAR-REB-YOEL/`.
2. **Netlify Drop (העלאה מיידית בגרירה בדפדפן):**
   - גרור את תיקיית `dist` אל https://app.netlify.com/drop .
3. **Cloudflare Pages (חינמי עם רוחב פס ללא הגבלה):**
   - הרץ `npx wrangler pages deploy dist --project-name=reb-yoel-archive` והתחבר בחלון הדפדפן שייפתח.

## חיבור Google Form לשליחת משוב ומאגרים
פתח את הקובץ `config.js` והדבק את הקישור ל-Google Form שיצרת ב-`googleFormArchiveUrl` ו-`googleFormFeedbackUrl`.
