/**
 * Structured multilingual dictionary for BolKhata AI.
 * Covers Kannada (ಕನ್ನಡ), Hindi (हिन्दी), and Indian English.
 */

import { SupportedLanguage } from '../types/api';

export interface TranslationDictionary {
  appName: string;
  tagline: string;
  nav: {
    dashboard: string;
    customers: string;
    voiceKhata: string;
    refresh: string;
  };
  metrics: {
    outstandingBalance: string;
    totalPayments: string;
    activeCustomers: string;
    totalTransactions: string;
    rupeeSymbol: string;
  };
  voice: {
    pressToTalk: string;
    releaseToStop: string;
    listening: string;
    processing: string;
    tapToRecord: string;
    recordingDuration: string;
    audioPreview: string;
    discardAudio: string;
    micPermissionDenied: string;
    micUnavailable: string;
    emptyRecording: string;
    quickExamples: string;
    customUtterancePlaceholder: string;
    parseButton: string;
    phase5Notice: string;
  };
  proposal: {
    title: string;
    customer: string;
    intent: string;
    amount: string;
    actionSummary: string;
    requiresConfirmation: string;
    confirmButton: string;
    confirming: string;
    rejectButton: string;
    rejectReasonPrompt: string;
    statusPending: string;
    statusCommitted: string;
    statusRejected: string;
    statusExpired: string;
    replayNotice: string;
    readOnlyNotice: string;
    clarificationPrompt: string;
    stagedSuccess: string;
  };
  disambiguation: {
    title: string;
    subtitle: string;
    selectPrompt: string;
    createNewPrompt: string;
    selectButton: string;
  };
  customer: {
    title: string;
    searchPlaceholder: string;
    addCustomer: string;
    customerName: string;
    phoneNumber: string;
    cancel: string;
    save: string;
    noCustomersFound: string;
    totalCredit: string;
    totalPayment: string;
    currentBalance: string;
    viewHistory: string;
    ledgerHistory: string;
    noEntriesFound: string;
    entryCredit: string;
    entryPayment: string;
    dateTime: string;
    refId: string;
  };
  general: {
    loading: string;
    retry: string;
    error: string;
    success: string;
    dismiss: string;
    backendOnline: string;
    backendOffline: string;
    storeContext: string;
  };
}

export const translations: Record<SupportedLanguage, TranslationDictionary> = {
  kn: {
    appName: 'ಬೋಲ್ ಖಾತಾ AI',
    tagline: 'ನಿಮ್ಮ ಕಿರಾಣಿ ಅಂಗಡಿ. ನಿಮ್ಮ ಧ್ವನಿ. ನಿಮ್ಮ ಡಿಜಿಟಲ್ ಖಾತಾ.',
    nav: {
      dashboard: 'ಮುಖಪುಟ',
      customers: 'ಗ್ರಾಹಕರು',
      voiceKhata: 'ಧ್ವನಿ ಖಾತಾ',
      refresh: 'ನವೀಕರಿಸಿ',
    },
    metrics: {
      outstandingBalance: 'ಒಟ್ಟು ಬಾಕಿ ಉದಾರ್',
      totalPayments: 'ಒಟ್ಟು ಜಮಾ ಸ್ವೀಕರಿಸಲಾಗಿದೆ',
      activeCustomers: 'ಸಕ್ರಿಯ ಗ್ರಾಹಕರು',
      totalTransactions: 'ಒಟ್ಟು ವಹಿವಾಟುಗಳು',
      rupeeSymbol: '₹',
    },
    voice: {
      pressToTalk: 'ಮಾತನಾಡಲು ಒತ್ತಿ ಹಿಡಿಯಿರಿ',
      releaseToStop: 'ನಿಲ್ಲಿಸಲು ಕೈಬಿಡಿ',
      listening: 'ಕೇಳಿಸಿಕೊಳ್ಳಲಾಗುತ್ತಿದೆ...',
      processing: 'ಧ್ವನಿ ಪ್ರಕ್ರಿಯೆಗೊಳಿಸಲಾಗುತ್ತಿದೆ...',
      tapToRecord: 'ರೆಕಾರ್ಡ್ ಮಾಡಲು ಟ್ಯಾಪ್ ಮಾಡಿ',
      recordingDuration: 'ಅವಧಿ',
      audioPreview: 'ರೆಕಾರ್ಡ್ ಮಾಡಿದ ಧ್ವನಿ ಪ್ಲೇ ಮಾಡಿ',
      discardAudio: 'ಧ್ವನಿ ರದ್ದುಗೊಳಿಸಿ',
      micPermissionDenied: 'ಮೈಕ್ರೊಫೋನ್ ಅನುಮತಿ ನಿರಾಕರಿಸಲಾಗಿದೆ. ಬ್ರೌಸರ್ ಸೆಟ್ಟಿಂಗ್ಸ್‌ನಲ್ಲಿ ಅನುಮತಿಸಿ.',
      micUnavailable: 'ಮೈಕ್ರೊಫೋನ್ ಸಾಧನ ಲಭ್ಯವಿಲ್ಲ.',
      emptyRecording: 'ಧ್ವನಿ ಗ್ರಹಿಸಲಾಗಿಲ್ಲ. ದಯವಿಟ್ಟು ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡಿ.',
      quickExamples: 'ಧ್ವನಿ ಉದಾಹರಣೆಗಳು',
      customUtterancePlaceholder: 'ಅಥವಾ ಧ್ವನಿ ಆಜ್ಞೆಯನ್ನು ಟೈಪ್ ಮಾಡಿ (ಉದಾ: ರಮೇಶ್ ಗೆ 340 ರೂಪಾಯಿ ಉದಾರ್ ಬರೆಯಿರಿ)',
      parseButton: 'ಖಾತಾಗೆ ಕಳುಹಿಸಿ',
      phase5Notice: 'ಫೇಸ್ 4: ಬ್ರೌಸರ್ ಆಡಿಯೋ ಸಂಗ್ರಹ ಮತ್ತು HITL ಪರಿಶೀಲನೆ. ಫೇಸ್ 5 ನಲ್ಲಿ ಜ್ಞಾನಿ ರಿಯಲ್-ಟೈಮ್ ಸ್ಟ್ರೀಮಿಂಗ್ ಸೇರಿಸಲಾಗುತ್ತದೆ.',
    },
    proposal: {
      title: 'ವಹಿವಾಟು ಪ್ರಸ್ತಾವನೆ ಪರಿಶೀಲನೆ',
      customer: 'ಗ್ರಾಹಕರ ಹೆಸರು',
      intent: 'ಉದ್ದೇಶ',
      amount: 'ಮೊತ್ತ',
      actionSummary: 'ಪ್ರಸ್ತಾವಿತ ವಿವರ',
      requiresConfirmation: 'ಅಂಗಡಿಯವರ ದೃಢೀಕರಣ ಅಗತ್ಯವಿದೆ',
      confirmButton: 'ದೃಢೀಕರಿಸಿ (ಖಾತಾಗೆ ಸೇರಿಸಿ)',
      confirming: 'ಸೇರಿಸಲಾಗುತ್ತಿದೆ...',
      rejectButton: 'ತಿರಸ್ಕರಿಸಿ / ರದ್ದುಗೊಳಿಸಿ',
      rejectReasonPrompt: 'ರದ್ದತಿಗೆ ಕಾರಣ ನಮೂದಿಸಿ (ಐಚ್ಛಿಕ)',
      statusPending: 'ದೃಢೀಕರಣಕ್ಕಾಗಿ ಕಾಯುತ್ತಿದೆ',
      statusCommitted: 'ದೃಢೀಕರಿಸಲಾಗಿದೆ',
      statusRejected: 'ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ',
      statusExpired: 'ಅವಧಿ ಮೀರಿದೆ',
      replayNotice: 'ಈ ವಹಿವಾಟು ಈಗಾಗಲೇ ದಾಖಲಾಗಿದೆ (ನಕಲು ತಡೆಗಟ್ಟಲಾಗಿದೆ).',
      readOnlyNotice: 'ಇದು ಕೇವಲ ಮಾಹಿತಿ ವೀಕ್ಷಣೆ (ಹಣಕಾಸು ಬದಲಾವಣೆ ಇಲ್ಲ).',
      clarificationPrompt: 'ಆಜ್ಞೆ ಸ್ಪಷ್ಟವಾಗಿಲ್ಲ. ದಯವಿಟ್ಟು ಗ್ರಾಹಕರ ಹೆಸರು ಮತ್ತು ಮೊತ್ತವನ್ನು ತಿಳಿಸಿ.',
      stagedSuccess: 'ಪ್ರಸ್ತಾವನೆ ರಚಿಸಲಾಗಿದೆ. ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ ದೃಢೀಕರಿಸಿ.',
    },
    disambiguation: {
      title: 'ಗ್ರಾಹಕರ ಆಯ್ಕೆ ಅಗತ್ಯವಿದೆ',
      subtitle: 'ಈ ಹೆಸರಿಗೆ ಹಲವು ಗ್ರಾಹಕರು ಲಭ್ಯವಿದ್ದಾರೆ. ದಯವಿಟ್ಟು ಸರಿಯಾದ ಗ್ರಾಹಕರನ್ನು ಆರಿಸಿ.',
      selectPrompt: 'ಖಾತೆ ಆಯ್ಕೆಮಾಡಿ',
      createNewPrompt: 'ಹೊಸ ಗ್ರಾಹಕರನ್ನಾಗಿ ರಚಿಸಿ',
      selectButton: 'ಈ ಗ್ರಾಹಕರನ್ನು ಆಯ್ಕೆಮಾಡಿ',
    },
    customer: {
      title: 'ಗ್ರಾಹಕರ ಪಟ್ಟಿ',
      searchPlaceholder: 'ಹೆಸರು ಅಥವಾ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ಹುಡುಕಿ...',
      addCustomer: 'ಹೊಸ ಗ್ರಾಹಕ ಸೇರಿಸಿ',
      customerName: 'ಗ್ರಾಹಕರ ಹೆಸರು',
      phoneNumber: 'ಮೊಬೈಲ್ ಸಂಖ್ಯೆ',
      cancel: 'ರದ್ದು',
      save: 'ಉಳಿಸಿ',
      noCustomersFound: 'ಯಾವುದೇ ಗ್ರಾಹಕರು ಕಂಡುಬಂದಿಲ್ಲ.',
      totalCredit: 'ಒಟ್ಟು ಉದಾರ್',
      totalPayment: 'ಒಟ್ಟು ಜಮಾ',
      currentBalance: 'ಪ್ರಸ್ತುತ ಬಾಕಿ',
      viewHistory: 'ಖಾತಾ ಇತಿಹಾಸ ವೀಕ್ಷಿಸಿ',
      ledgerHistory: 'ವಹಿವಾಟು ಇತಿಹಾಸ',
      noEntriesFound: 'ಇನ್ನೂ ಯಾವುದೇ ವಹಿವಾಟುಗಳಿಲ್ಲ.',
      entryCredit: 'ಉದಾರ್ (+)',
      entryPayment: 'ಜಮಾ (-)',
      dateTime: 'ದಿನಾಂಕ & ಸಮಯ',
      refId: 'ರೆಫರೆನ್ಸ್ ಐಡಿ',
    },
    general: {
      loading: 'ಲೋಡ್ ಆಗುತ್ತಿದೆ...',
      retry: 'ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ',
      error: 'ದೋಷ ಸಂಭವಿಸಿದೆ',
      success: 'ಯಶಸ್ವಿಯಾಗಿದೆ',
      dismiss: 'ಮುಚ್ಚಿ',
      backendOnline: 'ಬ್ಯಾಕೆಂಡ್ ಸಂಪರ್ಕಗೊಂಡಿದೆ',
      backendOffline: 'ಬ್ಯಾಕೆಂಡ್ ಆಫ್‌ಲೈನ್',
      storeContext: 'ಕಿರಾಣಿ ಅಂಗಡಿ ID',
    },
  },

  hi: {
    appName: 'बोल खाता AI',
    tagline: 'आपकी किराना दुकान। आपकी आवाज़। आपका डिजिटल खाता।',
    nav: {
      dashboard: 'डैशबोर्ड',
      customers: 'ग्राहक',
      voiceKhata: 'आवाज़ खाता',
      refresh: 'रिफ्रेश',
    },
    metrics: {
      outstandingBalance: 'कुल बकाया उधार',
      totalPayments: 'कुल जमा राशि',
      activeCustomers: 'सक्रिय ग्राहक',
      totalTransactions: 'कुल लेन-देन',
      rupeeSymbol: '₹',
    },
    voice: {
      pressToTalk: 'बोलने के लिए दबाकर रखें',
      releaseToStop: 'रोकने के लिए छोड़ें',
      listening: 'सुन रहे हैं...',
      processing: 'आवाज़ प्रोसेस हो रही है...',
      tapToRecord: 'रिकॉर्ड करने के लिए टैप करें',
      recordingDuration: 'समय',
      audioPreview: 'रिकॉर्ड की गई आवाज़ सुनें',
      discardAudio: 'रद्द करें',
      micPermissionDenied: 'माइक्रोफ़ोन की अनुमति अस्वीकृत है। कृपया ब्राउज़र सेटिंग्स में अनुमति दें।',
      micUnavailable: 'माइक्रोफ़ोन उपलब्ध नहीं है।',
      emptyRecording: 'आवाज़ रिकॉर्ड नहीं हुई। कृपया स्पष्ट बोलें।',
      quickExamples: 'आवाज़ के उदाहरण',
      customUtterancePlaceholder: 'या आवाज़ कमांड टाइप करें (उदा: रमेश के नाम 340 रुपये उधार लिखो)',
      parseButton: 'खाते में भेजें',
      phase5Notice: 'फ़ेज़ 4: ब्राउज़र ऑडियो रिकॉर्डिंग और HITL पुष्टि। फ़ेज़ 5 में ज्ञानी रियल-टाइम स्ट्रीमिंग जुड़ेगी।',
    },
    proposal: {
      title: 'लेन-देन प्रस्ताव समीक्षा',
      customer: 'ग्राहक का नाम',
      intent: 'प्रकार',
      amount: 'राशि',
      actionSummary: 'प्रस्तावित विवरण',
      requiresConfirmation: 'दुकानदार की पुष्टि आवश्यक है',
      confirmButton: 'पुष्टि करें (खाते में दर्ज करें)',
      confirming: 'दर्ज हो रहा है...',
      rejectButton: 'अस्वीकार करें / रद्द करें',
      rejectReasonPrompt: 'रद्द करने का कारण दर्ज करें (वैकल्पिक)',
      statusPending: 'पुष्टि की प्रतीक्षा है',
      statusCommitted: 'सफलतापूर्वक दर्ज',
      statusRejected: 'रद्द किया गया',
      statusExpired: 'समय समाप्त',
      replayNotice: 'यह लेन-देन पहले ही दर्ज हो चुका है (डुप्लीकेट रोका गया)।',
      readOnlyNotice: 'यह केवल जानकारी है (वित्तीय खाते में बदलाव नहीं)।',
      clarificationPrompt: 'कमांड स्पष्ट नहीं है। कृपया ग्राहक का नाम और राशि स्पष्ट करें।',
      stagedSuccess: 'प्रस्ताव तैयार है। कृपया जांच कर पुष्टि करें।',
    },
    disambiguation: {
      title: 'ग्राहक का चयन करें',
      subtitle: 'इस नाम के एक से अधिक ग्राहक मौजूद हैं। कृपया सही ग्राहक चुनें।',
      selectPrompt: 'खाता चुनें',
      createNewPrompt: 'नया ग्राहक बनाएं',
      selectButton: 'इस ग्राहक को चुनें',
    },
    customer: {
      title: 'ग्राहकों की सूची',
      searchPlaceholder: 'नाम या मोबाइल नंबर खोजें...',
      addCustomer: 'नया ग्राहक जोड़ें',
      customerName: 'ग्राहक का नाम',
      phoneNumber: 'मोबाइल नंबर',
      cancel: 'रद्द करें',
      save: 'सुरक्षित करें',
      noCustomersFound: 'कोई ग्राहक नहीं मिला।',
      totalCredit: 'कुल उधार',
      totalPayment: 'कुल जमा',
      currentBalance: 'वर्तमान बकाया',
      viewHistory: 'खाता इतिहास देखें',
      ledgerHistory: 'लेन-देन इतिहास',
      noEntriesFound: 'अभी कोई लेन-देन नहीं है।',
      entryCredit: 'उधार (+)',
      entryPayment: 'जमा (-)',
      dateTime: 'दिनांक और समय',
      refId: 'रेफरेंस आईडी',
    },
    general: {
      loading: 'लोड हो रहा है...',
      retry: 'पुनः प्रयास करें',
      error: 'त्रुटि हुई',
      success: 'सफल',
      dismiss: 'बंद करें',
      backendOnline: 'बैकएंड कनेक्टेड',
      backendOffline: 'बैकएंड ऑफलाइन',
      storeContext: 'किराना स्टोर ID',
    },
  },

  en: {
    appName: 'BolKhata AI',
    tagline: 'Your Kirana Store. Your Voice. Your Digital Khata.',
    nav: {
      dashboard: 'Dashboard',
      customers: 'Customers',
      voiceKhata: 'Voice Khata',
      refresh: 'Refresh',
    },
    metrics: {
      outstandingBalance: 'Total Outstanding Credit',
      totalPayments: 'Total Payments Received',
      activeCustomers: 'Active Customers',
      totalTransactions: 'Total Transactions',
      rupeeSymbol: '₹',
    },
    voice: {
      pressToTalk: 'Hold to Speak',
      releaseToStop: 'Release to Stop',
      listening: 'Listening...',
      processing: 'Processing voice...',
      tapToRecord: 'Tap to Record',
      recordingDuration: 'Duration',
      audioPreview: 'Play Recorded Audio',
      discardAudio: 'Discard Audio',
      micPermissionDenied: 'Microphone permission denied. Please allow microphone access in browser settings.',
      micUnavailable: 'Microphone hardware is not available.',
      emptyRecording: 'No voice audio detected. Please speak clearly.',
      quickExamples: 'Voice Command Examples',
      customUtterancePlaceholder: 'Or type voice command (e.g. Add 340 rupees credit for Ramesh)',
      parseButton: 'Process Command',
      phase5Notice: 'Phase 4: Browser audio capture & HITL confirmation. Gnani real-time streaming connects in Phase 5.',
    },
    proposal: {
      title: 'Transaction Proposal Review',
      customer: 'Customer Name',
      intent: 'Intent',
      amount: 'Amount',
      actionSummary: 'Proposed Action',
      requiresConfirmation: 'Merchant Confirmation Required',
      confirmButton: 'Confirm Transaction (Post to Ledger)',
      confirming: 'Posting to Ledger...',
      rejectButton: 'Reject / Cancel',
      rejectReasonPrompt: 'Optional rejection reason',
      statusPending: 'Awaiting Confirmation',
      statusCommitted: 'Committed to Ledger',
      statusRejected: 'Rejected',
      statusExpired: 'Proposal Expired',
      replayNotice: 'Transaction already committed. Replay response returned (no duplicate credit).',
      readOnlyNotice: 'Informational query only. No financial mutation will be performed.',
      clarificationPrompt: 'Utterance unclear. Please specify customer name and transaction amount.',
      stagedSuccess: 'Proposal staged server-side. Please review and confirm.',
    },
    disambiguation: {
      title: 'Customer Disambiguation Required',
      subtitle: 'Multiple customers found matching this name. Please select the correct record.',
      selectPrompt: 'Select Account',
      createNewPrompt: 'Create as New Customer',
      selectButton: 'Select This Customer',
    },
    customer: {
      title: 'Customer Directory',
      searchPlaceholder: 'Search by name or phone...',
      addCustomer: 'Add New Customer',
      customerName: 'Customer Name',
      phoneNumber: 'Phone Number',
      cancel: 'Cancel',
      save: 'Save Customer',
      noCustomersFound: 'No customers found.',
      totalCredit: 'Total Udhaar',
      totalPayment: 'Total Jama',
      currentBalance: 'Outstanding Balance',
      viewHistory: 'View Ledger History',
      ledgerHistory: 'Transaction Ledger',
      noEntriesFound: 'No ledger entries recorded yet.',
      entryCredit: 'Credit (+)',
      entryPayment: 'Payment (-)',
      dateTime: 'Date & Time',
      refId: 'Ref ID',
    },
    general: {
      loading: 'Loading...',
      retry: 'Retry',
      error: 'Error occurred',
      success: 'Success',
      dismiss: 'Dismiss',
      backendOnline: 'Backend Online',
      backendOffline: 'Backend Offline',
      storeContext: 'Kirana Store ID',
    },
  },
};
