// הגדרות שליחת פידבק ומאגרים חדשים (Google Forms / GitHub Issues / Formspree / Mailto)
window.SITE_CONFIG = {
  // === מומלץ: חיבור ל-Google Form ===
  // 1. צור Google Form ב-https://forms.google.com -> לחץ "שלח" (Send) -> סמל הקישור -> העתק את הקישור והדבק כאן:
  googleFormArchiveUrl: "",
  googleFormFeedbackUrl: "",

  // 2. אופציונלי מתקדם (שליחה אוטומטית ברקע ישירות מהטופס המובנה באתר ל-Google Sheets):
  // אם תרצה שליחה שקטה מהטופס המעוצב של האתר ישירות לטופס גוגל, הכנס כאן אובייקט של מזהי השדות (entry.123456)
  googleFormArchiveEntries: null,
  googleFormFeedbackEntries: null,

  // === ערוצים חלופיים (אופציונלי) ===
  contactEmail: "",
  githubRepo: "",
  formEndpoint: "",
};
