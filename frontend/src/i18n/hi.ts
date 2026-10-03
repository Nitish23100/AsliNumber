import type { Strings } from "./en";

/**
 * Hindi strings for the Login page, matching every key in `en.ts`.
 * Per Requirement 12.6 / docs/design.md section 9: shipped alongside
 * English from the start, not added later.
 */
export const hi: Strings = {
  pageTitle: "लॉग इन करें",
  emailLabel: "ईमेल",
  passwordLabel: "पासवर्ड",
  submitButton: "लॉग इन करें",
  submittingButton: "लॉग इन हो रहा है...",
  loginFailedError: "यह ईमेल या पासवर्ड हमारे रिकॉर्ड से मेल नहीं खाता।",
  emailRequiredError: "अपना ईमेल दर्ज करें।",
  passwordRequiredError: "अपना पासवर्ड दर्ज करें।",
  statusApiLabel: "API उपलब्ध है",
  statusMongoOkLabel: "डेटाबेस कनेक्ट है",
  statusMongoUnavailableLabel: "डेटाबेस अनुपलब्ध है",
  statusRoleLabel: (role: string) => `${role} के रूप में साइन इन`,
};
