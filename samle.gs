// ===================================================================
// グローバル変数
// ===================================================================
const PROCESSED_EVENTS_KEY = 'PROCESSED_EVENTS';

// ===================================================================
// メインハンドラ (Slackからの全リクエストの入口)
// ===================================================================
/**
 * SlackからのPOSTリクエストを処理します。
 * @param {object} e - イベントオブジェクト
 * @return {object} - ContentServiceオブジェクト
 */
function doPost(e) {
  try {
    // ボタンクリックなどの対話操作を処理
    if (e.parameter.payload) {
      const payload = JSON.parse(e.parameter.payload);
      if (payload.type === 'block_actions') {
        processBlockActions(payload);
      }
      return ContentService.createTextOutput('OK').setMimeType(ContentService.MimeType.TEXT);
    }

    const requestBody = JSON.parse(e.postData.contents);
    
    // イベント情報をログ出力（デバッグ用）
    if (requestBody.event) {
      console.log(`受信イベント: Type=${requestBody.event.type}, Channel=${requestBody.event.channel_type}, Text=${requestBody.event.text?.substring(0, 50)}`);
    }

    // Slack APIのURL検証（初回設定時のみ）
    if (requestBody.type === 'url_verification') {
      return ContentService.createTextOutput(requestBody.challenge).setMimeType(ContentService.MimeType.TEXT);
    }

    // 通常のメッセージイベントを処理
    if (requestBody.type === 'event_callback') {
      // 重複実行を防止しつつ、非同期でイベントを処理
      if (shouldProcessEvent(requestBody)) {
        processSlackEventAsync(requestBody.event, requestBody.event_id);
      }
      return ContentService.createTextOutput('OK').setMimeType(ContentService.MimeType.TEXT);
    }

    return ContentService.createTextOutput('Unsupported request').setMimeType(ContentService.MimeType.TEXT);

  } catch (error) {
    console.error('doPost Error:', error, error.stack);
    return ContentService.createTextOutput('Error').setMimeType(ContentService.MimeType.TEXT);
  }
}

/**
 * GETリクエスト用のテスト関数です。
 */
function doGet(e) {
  return ContentService
    .createTextOutput('Slack Calendar Bot is running!')
    .setMimeType(ContentService.MimeType.TEXT);
}

// ===================================================================
// 統合処理：添付ファイル + 平文テキスト
// ===================================================================

/**
 * メインイベント処理（統合版）
 */
function processSlackEventAsync(event, eventId) {
  try {
    console.log(`イベント処理開始: ${eventId}, Type: ${event.type}, Subtype: ${event.subtype}`);
    
    // ボット自身の発言は無視
    if (event.bot_id) return;
    
    // app_mentionイベントのみを処理（message.channelsイベントは無視）
    if (event.type !== 'app_mention' && event.type !== 'message') {
      console.log(`イベントタイプ ${event.type} はスキップします`);
      return;
    }
    
    // DMの場合はmessageイベントを処理、チャンネルの場合はapp_mentionのみ処理
    if (event.channel_type !== 'im' && event.type === 'message') {
      console.log('チャンネル内のmessageイベントはスキップします（app_mentionを待ちます）');
      return;
    }

    const { text, channel, user, channel_type } = event;

    // *** 統合処理：添付ファイル/URL + 平文テキストを組み合わせて処理 ***
    const combinedResult = processCombinedContent(event);
    
    if (combinedResult.hasContent) {
      console.log(`統合処理実行: ${combinedResult.sourceTypes.join(' + ')}`);
      handleCombinedScheduleExtraction(event, combinedResult);
      return;
    }

    // 添付ファイルもURLもない場合は、既存の平文テキスト処理
    if (!text) return;

    const intent = getIntent(text);

    switch (intent) {
      case 'check':
        handleCheckRequest(event);
        break;
      case 'delete':
        handleDeleteRequest(event);
        break;
      case 'modify':
        handleModifyRequest(event);
        break;
      case 'add':
        const isDM = channel_type === 'im';
        const isMention = text.includes('<@');
        if (isDM || isMention || isScheduleRequest(text)) {
           handleScheduleRequest(event);
        } else if (isHelpRequest(text)) {
           sendHelpMessage(channel, user);
        }
        break;
      default:
        if (channel_type === 'im' && isHelpRequest(text)) {
            sendHelpMessage(channel, user);
        }
        break;
    }
    console.log(`イベント処理完了: ${eventId}`);
  } catch (error) {
    console.error('processSlackEventAsync Error:', error, error.stack);
    sendSlackMessage(event.channel, `エラーが発生しました: ${error.message}`, event.user);
  }
}

/**
 * 添付ファイル/URL + 平文テキストの組み合わせを処理
 * @param {object} event - Slackイベント
 * @return {object} - 統合処理結果
 */
function processCombinedContent(event) {
  const result = {
    hasContent: false,
    sourceTypes: [],
    combinedText: '',
    fileInfo: null
  };

  const { text } = event;
  
  // 1. 各種ファイル/URLの検出
  const pdfFiles = extractPDFsFromSlackEvent(event);
  const wordFiles = extractWordFilesFromSlackEvent(event);
  const pptxFiles = extractPowerPointFilesFromSlackEvent(event);
  const urls = extractUrlsFromText(text);

  // 2. 何らかのファイル/URLが存在するかチェック
  if (pdfFiles.length > 0 || wordFiles.length > 0 || pptxFiles.length > 0 || urls.length > 0) {
    result.hasContent = true;
    
    // 平文テキストがある場合は追加
    if (text && text.trim().length > 0) {
      result.combinedText += `【ユーザーメッセージ】\n${text}\n\n`;
      result.sourceTypes.push('テキスト');
    }
    
    // ファイル情報を設定（優先順位: PDF > Word > PowerPoint）
    if (pdfFiles.length > 0) {
      result.fileInfo = { type: 'pdf', files: pdfFiles };
      result.sourceTypes.push('PDF');
    } else if (wordFiles.length > 0) {
      result.fileInfo = { type: 'word', files: wordFiles };
      result.sourceTypes.push('Word');
    } else if (pptxFiles.length > 0) {
      result.fileInfo = { type: 'powerpoint', files: pptxFiles };
      result.sourceTypes.push('PowerPoint');
    }
    
    // URL情報を設定
    if (urls.length > 0) {
      result.urlInfo = urls;
      result.sourceTypes.push('URL');
    }
  }

  return result;
}

/**
 * 統合された内容から予定情報を抽出して処理
 * @param {object} event - Slackイベント
 * @param {object} combinedResult - 統合処理結果
 */
function handleCombinedScheduleExtraction(event, combinedResult) {
  const { channel, user } = event;
  
  try {
    const sourceDescription = combinedResult.sourceTypes.join(' + ');
    sendSlackMessage(channel, `📋 ${sourceDescription}から予定情報を解析しています...`, user);
    
    let allExtractedText = combinedResult.combinedText;
    let primaryFileName = null;
    
    // ファイル処理
    if (combinedResult.fileInfo) {
      try {
        const fileResult = extractTextFromFile(combinedResult.fileInfo);
        allExtractedText += `【${fileResult.type}ファイル内容：${fileResult.fileName}】\n${fileResult.text}\n\n`;
        primaryFileName = fileResult.fileName;
      } catch (fileError) {
        console.error('ファイル処理エラー:', fileError);
        allExtractedText += `【ファイル処理エラー】\n${fileError.message}\n\n`;
      }
    }
    
    // URL処理
    if (combinedResult.urlInfo && combinedResult.urlInfo.length > 0) {
      for (const url of combinedResult.urlInfo.slice(0, 2)) { // 最大2つのURLまで
        try {
          const webContent = fetchWebPageContent(url);
          if (webContent && webContent.trim().length > 0) {
            allExtractedText += `【Webページ内容：${url}】\n${webContent}\n\n`;
          }
        } catch (urlError) {
          console.error('URL処理エラー:', urlError);
          allExtractedText += `【URL処理エラー：${url}】\n${urlError.message}\n\n`;
        }
      }
    }
    
    console.log(`統合テキスト準備完了: ${allExtractedText.length}文字`);
    
    if (!allExtractedText || allExtractedText.trim().length === 0) {
      sendSlackMessage(channel, '❌ 内容を取得できませんでした。', user);
      return;
    }
    
    // 統合された内容をGeminiで解析
    const scheduleData = parseScheduleFromCombinedContent(allExtractedText, sourceDescription);
    
    if (!scheduleData || scheduleData.length === 0) {
      sendSlackMessage(channel, `📋 ${sourceDescription}に予定情報は見つかりませんでした。`, user);
      return;
    }
    
    console.log(`📤 統合予定確認メッセージ送信: ${scheduleData.length}件`);
    
    // 単一予定の場合
    if (scheduleData.length === 1) {
      sendCombinedScheduleConfirmation(channel, user, scheduleData[0], sourceDescription, primaryFileName);
    } else {
      // 複数予定の場合
      sendMultipleCombinedScheduleConfirmation(channel, user, scheduleData, sourceDescription, primaryFileName);
    }
    
  } catch (error) {
    console.error('統合予定抽出エラー:', error);
    sendSlackMessage(channel, `❌ 解析中にエラーが発生しました: ${error.message}`, user);
  }
}

/**
 * ファイルからテキストを抽出（ファイルタイプに応じて処理）
 * @param {object} fileInfo - ファイル情報
 * @return {object} - {type: string, fileName: string, text: string}
 */
function extractTextFromFile(fileInfo) {
  const targetFile = fileInfo.files[0];
  
  switch (fileInfo.type) {
    case 'pdf':
      const pdfData = downloadPDFFromSlack(targetFile);
      const pdfText = extractTextFromPDF(pdfData, targetFile.name);
      return { type: 'PDF', fileName: targetFile.name, text: pdfText };
      
    case 'word':
      const wordData = downloadWordFromSlack(targetFile);
      const wordText = extractTextFromDocxBasicDrive(wordData, targetFile.name);
      return { type: 'Word', fileName: targetFile.name, text: wordText };
      
    case 'powerpoint':
      const pptxData = downloadPowerPointFromSlack(targetFile);
      const pptxText = extractTextFromPptxBasicDrive(pptxData, targetFile.name);
      return { type: 'PowerPoint', fileName: targetFile.name, text: pptxText };
      
    default:
      throw new Error(`未対応のファイルタイプ: ${fileInfo.type}`);
  }
}

/**
 * 統合されたコンテンツから予定情報を解析（Gemini強化版）
 * @param {string} combinedContent - 統合されたテキストコンテンツ
 * @param {string} sourceDescription - 情報源の説明
 * @return {Array<object>} - 抽出された予定データの配列
 */
function parseScheduleFromCombinedContent(combinedContent, sourceDescription) {
  const now = new Date();
  const currentDate = Utilities.formatDate(now, 'Asia/Tokyo', 'yyyy-MM-dd HH:mm (E)');
  
  const prompt = `
現在の日時: ${currentDate}
以下の統合された情報から、予定・イベント・会議などの情報を抽出してください。

情報源: ${sourceDescription}

統合コンテンツ:
${combinedContent}

重要なルール:
1. 【ユーザーメッセージ】【ファイル内容】【Webページ内容】の全ての情報を総合的に判断
2. 同じ予定について複数の情報源で言及されている場合は、1つの予定として統合
3. ユーザーメッセージで具体的な指示がある場合は、それを優先
4. ファイルやWebページの情報で詳細が補完できる場合は活用
5. 期間を表す表現（「○日から○日まで」「○日〜○日」「3日間の」等）は、必ず1つのイベントとして扱う
6. 複数日イベントの場合、必ずendDateに最終日を設定する

抽出項目（予定ごとに）:
- title: 予定のタイトル（最も詳細で正確な情報を使用）
- date: 開始日 (YYYY-MM-DD形式、年が明記されていない場合は2025年と仮定)
- endDate: 終了日 (YYYY-MM-DD形式、単日の場合はnull、複数日の場合は最終日)
- startTime: 開始時間 (HH:MM形式、不明な場合はnull)
- endTime: 終了時間 (HH:MM形式、不明な場合はnull)
- isAllDay: 終日イベントか (true/false)
- location: 開催場所（オンライン、住所、会議室名など）
- description: 詳細説明（複数の情報源から得られた情報を統合）
- sourceInfo: "${sourceDescription}"

統合例:
- ユーザーメッセージ: 「明日の会議の詳細を送ります」
- PDFファイル: 「プロジェクト会議 2025年7月12日 14:00-16:00 会議室A」
→ 1つの統合された予定として処理

重複排除のルール:
- 同じタイトルで同じ日付の予定は1つにまとめる
- より詳細な情報を持つ方を採用
- 複数の情報源で補完し合う場合は統合

その他のルール:
1. 予定が複数ある場合は配列で返す
2. 日付が過去の場合は除外する
3. 明確な予定情報がない場合は空配列[]を返す
4. 時間が不明な場合はisAllDay: trueとする
5. 年が記載されていない場合は2025年と仮定

JSON配列のみを返してください（説明や\`\`\`は不要）:`;

  try {
    const result = callGemini(prompt);
    
    // 結果が配列でない場合は配列に変換
    const scheduleArray = Array.isArray(result) ? result : (result ? [result] : []);
    
    // 有効な予定のみをフィルタリング
    const validSchedules = scheduleArray.filter(schedule => {
      return schedule && 
             schedule.title && 
             schedule.date && 
             /^\d{4}-\d{2}-\d{2}$/.test(schedule.date);
    });
    
    console.log(`${validSchedules.length}件の有効な予定を抽出しました（統合処理）`);
    
    // デバッグ：抽出された予定の詳細をログ出力
    validSchedules.forEach((schedule, index) => {
      console.log(`統合予定${index + 1}: ${schedule.title} (${schedule.date}${schedule.endDate ? ' 〜 ' + schedule.endDate : ''})`);
    });
    
    return validSchedules;
    
  } catch (error) {
    console.error('統合コンテンツ解析エラー:', error);
    throw new Error(`予定情報の解析に失敗しました: ${error.message}`);
  }
}

/**
 * 統合処理由来の単一予定の確認メッセージを送信
 */
function sendCombinedScheduleConfirmation(channel, user, scheduleData, sourceDescription, fileName) {
  const { title, date, endDate, startTime, endTime, isAllDay, location, description } = scheduleData;
  
  // 日時の表示形式を整える
  let timeText = '';
  if (isAllDay) {
    if (endDate && endDate !== date) {
      const startDateFormatted = Utilities.formatDate(new Date(date), 'Asia/Tokyo', 'M月d日(E)');
      const endDateFormatted = Utilities.formatDate(new Date(endDate), 'Asia/Tokyo', 'M月d日(E)');
      const days = Math.ceil((new Date(endDate) - new Date(date)) / (1000 * 60 * 60 * 24)) + 1;
      timeText = `${startDateFormatted} 〜 ${endDateFormatted}（${days}日間・終日）`;
    } else {
      const eventDate = Utilities.formatDate(new Date(date), 'Asia/Tokyo', 'M月d日(E)');
      timeText = `${eventDate}（終日）`;
    }
  } else {
    const eventDate = Utilities.formatDate(new Date(date), 'Asia/Tokyo', 'M月d日(E)');
    const start = startTime || '時間未定';
    const end = endTime || '';
    timeText = end ? `${eventDate} ${start} 〜 ${end}` : `${eventDate} ${start}〜`;
  }
  
  let locationText = '';
  if (location) {
    locationText = `\n*📍 場所:* ${location}`;
  }
  
  let descriptionText = '';
  if (description) {
    const shortDescription = description.length > 100 ? 
      description.substring(0, 100) + '...' : description;
    descriptionText = `\n*📝 詳細:* ${shortDescription}`;
  }
  
  const fileNameText = fileName ? `\n*📎 ファイル:* ${fileName}` : '';
  const confirmationText = `*📅 予定名:* ${title}\n*🕐 日時:* ${timeText}${locationText}${descriptionText}\n*📋 情報源:* ${sourceDescription}${fileNameText}`;
  
  const value = { 
    action: 'add_from_combined', 
    eventData: scheduleData 
  };
  
  const blocks = [{
    type: 'section', 
    text: { type: 'mrkdwn', text: `<@${user}> 📋 ${sourceDescription}から予定を検出しました！\n\n${confirmationText}` }
  }, {
    type: 'actions', 
    elements: [{
      type: 'button', 
      text: { type: 'plain_text', text: '📅 この予定を追加' },
      style: 'primary',
      action_id: 'confirm_add_from_combined', 
      value: JSON.stringify(value)
    }, {
      type: 'button', 
      text: { type: 'plain_text', text: '❌ 無視する' },
      action_id: 'cancel_action'
    }]
  }];
  
  sendSlackMessage(channel, `${sourceDescription}から予定を検出しました。`, null, { blocks: blocks });
}

/**
 * 統合処理由来の複数予定の確認メッセージを送信
 */
function sendMultipleCombinedScheduleConfirmation(channel, user, scheduleDataArray, sourceDescription, fileName) {
  try {
    const simpleMessage = `✅ ${sourceDescription}から${scheduleDataArray.length}件の予定を検出しました！\n\n` +
      scheduleDataArray.map((s, i) => `${i + 1}. ${s.title.substring(0, 40)}... (${s.date})`).join('\n') +
      (fileName ? `\n\n📎 ファイル: ${fileName}` : '') +
      `\n📋 情報源: ${sourceDescription}`;
    
    sendSlackMessage(channel, simpleMessage, user);
    console.log(`✅ 統合複数予定メッセージ送信完了`);
  } catch (error) {
    console.error('❌ 統合複数予定メッセージ送信エラー:', error);
    sendSlackMessage(channel, `✅ 解析完了！手動で確認してください。`, user);
  }
}

/**
 * 統合処理由来の予定追加成功メッセージを作成
 */
function createCombinedScheduleSuccessMessage(event, userId, sourceDescription, fileName) {
  let timeText = '';
  if (event.isAllDay) {
    if (event.endDate && event.endDate !== Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'yyyy-MM-dd')) {
      const startDateFormatted = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      const endDateFormatted = Utilities.formatDate(new Date(event.endDate), 'Asia/Tokyo', 'M月d日(E)');
      const days = Math.ceil((new Date(event.endDate) - event.startTime) / (1000 * 60 * 60 * 24)) + 1;
      timeText = `*🗓️ 期間:* ${startDateFormatted} 〜 ${endDateFormatted}（${days}日間・終日）`;
    } else {
      const eventDate = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      timeText = `*🗓️ 日付:* ${eventDate}（終日）`;
    }
  } else {
    const startTime = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E) HH:mm');
    const endTime = Utilities.formatDate(event.endTime, 'Asia/Tokyo', 'HH:mm');
    timeText = `*🕐 日時:* ${startTime} 〜 ${endTime}`;
  }

  let locationText = '';
  if (event.location) {
    locationText = `\n*📍 場所:* ${event.location}`;
  }
  
  const fileNameText = fileName ? `\n*📎 ファイル:* ${fileName}` : '';

  const blocks = [{
    type: 'section',
    text: { type: 'mrkdwn', text: `<@${userId}> ✅ ${sourceDescription}から予定を追加しました！\n\n*📅 予定名:* ${event.title}\n${timeText}${locationText}\n*📋 情報源:* ${sourceDescription}${fileNameText}` }
  }, {
    type: 'actions', 
    elements: [{
      type: 'button', 
      text: { type: 'plain_text', text: 'カレンダーで確認' },
      action_id: 'open_calendar',
      style: 'primary',
      value: JSON.stringify({ 
        action: 'open_calendar', 
        url: event.htmlLink || 'https://calendar.google.com/calendar',
        eventTitle: event.title 
      })
    }]
  }];
  return { blocks: blocks };
}

/**
 * ユーザーのメッセージから意図を判定します。
 * @param {string} text - ユーザーの入力テキスト
 * @return {string} - 'check', 'add', 'modify', 'delete', または 'unknown'
 */
function getIntent(text) {
  if (!text) return 'unknown';
  const lowerText = text.toLowerCase();

  if (/教えて|確認|何がある|いつ$|表示/.test(lowerText)) {
    return 'check';
  }
  if (/削除|キャンセル|取り消し|消して/.test(lowerText)) {
    return 'delete';
  }
  if (/変更|修正|移動|変えて|移して/.test(lowerText)) {
    return 'modify';
  }
  if (containsScheduleInfo(lowerText)) {
      return 'add';
  }
  return 'unknown';
}

// ===================================================================
// Wordファイル読み取り機能
// ===================================================================

/**
 * SlackイベントからWordファイル情報を抽出
 * @param {object} event - Slackイベント
 * @return {Array} - Wordファイル情報の配列
 */
function extractWordFilesFromSlackEvent(event) {
  if (event.files && event.files.length > 0) {
    return event.files.filter(file => 
      (file.mimetype === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' || 
       file.filetype === 'docx') && 
      file.size < 50 * 1024 * 1024 // 50MB制限
    );
  }
  return [];
}

/**
 * SlackからWordファイルをダウンロード
 * @param {object} fileInfo - Slackファイル情報
 * @return {Uint8Array} - Wordバイナリデータ
 */
function downloadWordFromSlack(fileInfo) {
  try {
    console.log(`📥 Slack Wordファイルダウンロード開始: ${fileInfo.name}`);
    console.log(`ファイル情報: サイズ=${fileInfo.size}, MIME=${fileInfo.mimetype}`);
    
    const response = UrlFetchApp.fetch(fileInfo.url_private, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${CONFIG.SLACK_BOT_TOKEN}`,
        'User-Agent': 'CalendarBot/1.0'
      },
      muteHttpExceptions: true,
      followRedirects: true
    });
    
    const responseCode = response.getResponseCode();
    console.log(`ダウンロード応答コード: ${responseCode}`);
    
    if (responseCode === 200) {
      const blob = response.getBlob();
      const downloadedData = blob.getBytes();
      
      console.log(`✅ Wordダウンロード成功: ${downloadedData.length} bytes`);
      
      // .docxヘッダーの確認（PKアーカイブ形式）
      console.log(`Wordヘッダー: ${Array.from(downloadedData.slice(0, 4)).map(b => b.toString(16)).join(' ')}`);
      
      // .docxファイルはZIPアーカイブなので、'PK'で始まる
      if (downloadedData[0] !== 0x50 || downloadedData[1] !== 0x4B) {
        console.warn(`⚠️ 無効なWordヘッダー検出`);
        // ただし、処理は続行（Slackが変換している可能性があるため）
      }
      
      return downloadedData;
    } else {
      const errorBody = response.getContentText();
      console.error(`Wordダウンロード失敗: ${responseCode}`);
      console.error(`エラー詳細: ${errorBody}`);
      throw new Error(`Slack Wordファイルダウンロード失敗: ${responseCode} - ${errorBody}`);
    }
  } catch (error) {
    console.error('Slack Wordファイルダウンロードエラー:', error);
    throw new Error(`Slackからのファイルダウンロードに失敗しました: ${error.message}`);
  }
}

/**
 * Word由来の単一予定追加成功メッセージを作成します
 * @param {object} event - 作成されたイベント
 * @param {string} userId - ユーザーID
 * @param {string} sourceFile - 元のWordファイル名
 * @return {object} - Slackメッセージ用のBlock Kitオブジェクト
 */
function createWordScheduleSuccessMessage(event, userId, sourceFile) {
  let timeText = '';
  if (event.isAllDay) {
    if (event.endDate && event.endDate !== Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'yyyy-MM-dd')) {
      const startDateFormatted = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      const endDateFormatted = Utilities.formatDate(new Date(event.endDate), 'Asia/Tokyo', 'M月d日(E)');
      const days = Math.ceil((new Date(event.endDate) - event.startTime) / (1000 * 60 * 60 * 24)) + 1;
      timeText = `*🗓️ 期間:* ${startDateFormatted} 〜 ${endDateFormatted}（${days}日間・終日）`;
    } else {
      const eventDate = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      timeText = `*🗓️ 日付:* ${eventDate}（終日）`;
    }
  } else {
    const startTime = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E) HH:mm');
    const endTime = Utilities.formatDate(event.endTime, 'Asia/Tokyo', 'HH:mm');
    timeText = `*🕐 日時:* ${startTime} 〜 ${endTime}`;
  }

  let locationText = '';
  if (event.location) {
    locationText = `\n*📍 場所:* ${event.location}`;
  }

  const blocks = [{
    type: 'section',
    text: { type: 'mrkdwn', text: `<@${userId}> ✅ Wordファイルから予定を追加しました！\n\n*📅 予定名:* ${event.title}\n${timeText}${locationText}\n*📄 情報源:* ${sourceFile}` }
  }, {
    type: 'actions', 
    elements: [{
      type: 'button', 
      text: { type: 'plain_text', text: 'カレンダーで確認' },
      action_id: 'open_calendar',
      style: 'primary',
      value: JSON.stringify({ 
        action: 'open_calendar', 
        url: event.htmlLink || 'https://calendar.google.com/calendar',
        eventTitle: event.title 
      })
    }]
  }];
  return { blocks: blocks };
}

/**
 * Drive API基本機能のみを使用してWordファイルからテキストを抽出
 * @param {Uint8Array} docxData - .docxファイルのバイナリデータ
 * @param {string} fileName - ファイル名
 * @return {string} - 抽出されたテキスト
 */
function extractTextFromDocxBasicDrive(docxData, fileName) {
  let tempFileId = null;
  
  try {
    console.log(`📄 Word処理開始（基本Drive API使用): ${fileName}`);
    
    // 1. 一時的にDriveにアップロード
    const blob = Utilities.newBlob(docxData, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', fileName);
    const tempFile = DriveApp.createFile(blob);
    tempFileId = tempFile.getId();
    
    console.log(`📤 一時ファイル作成成功: ${tempFileId}`);
    
    // 2. Google DocsとしてコピーしてテキストPDFを作成（export機能を使わない方法）
    const extractedText = extractTextFromUploadedDocx(tempFileId, fileName);
    
    if (!extractedText || extractedText.trim().length === 0) {
      throw new Error('Wordファイルからテキストを抽出できませんでした');
    }
    
    console.log(`✅ テキスト抽出完了: ${extractedText.length}文字`);
    return extractedText;
    
  } catch (error) {
    console.error('Word処理エラー:', error);
    throw new Error(`Wordファイルからのテキスト抽出に失敗しました: ${error.message}`);
  } finally {
    // 3. 一時ファイルを削除
    if (tempFileId) {
      try {
        DriveApp.getFileById(tempFileId).setTrashed(true);
        console.log(`🗑️ 一時ファイル削除完了: ${tempFileId}`);
      } catch (deleteError) {
        console.error('一時ファイル削除エラー:', deleteError);
      }
    }
  }
}

/**
 * アップロードされたWordファイルからテキストを抽出（複数手法で試行）
 * @param {string} fileId - DriveファイルID
 * @param {string} fileName - ファイル名
 * @return {string} - 抽出されたテキスト
 */
function extractTextFromUploadedDocx(fileId, fileName) {
  // 方法1: Document AIを使わずGoogle Docsに変換してコピー
  try {
    console.log(`📄 方法1: Google Docs変換によるテキスト抽出を試行`);
    
    // Google DocsとしてコピーしてHTMLで取得
    const copyRequest = {
      'name': `temp_conversion_${new Date().getTime()}`,
      'parents': [DriveApp.getRootFolder().getId()],
      'mimeType': 'application/vnd.google-apps.document'
    };
    
    const token = ScriptApp.getOAuthToken();
    
    // Drive APIでGoogle Docsとしてコピー
    const copyResponse = UrlFetchApp.fetch(
      `https://www.googleapis.com/drive/v3/files/${fileId}/copy`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        payload: JSON.stringify(copyRequest),
        muteHttpExceptions: true
      }
    );
    
    if (copyResponse.getResponseCode() === 200) {
      const copyResult = JSON.parse(copyResponse.getContentText());
      const docsId = copyResult.id;
      
      console.log(`📋 Google Docs作成成功: ${docsId}`);
      
      try {
        // Google DocsからHTML形式で取得
        const htmlResponse = UrlFetchApp.fetch(
          `https://www.googleapis.com/drive/v3/files/${docsId}/export?mimeType=text/html`,
          {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${token}`
            },
            muteHttpExceptions: true
          }
        );
        
        if (htmlResponse.getResponseCode() === 200) {
          const htmlContent = htmlResponse.getContentText();
          const textContent = extractTextFromHTML(htmlContent);
          
          // Google Docsファイルを削除
          DriveApp.getFileById(docsId).setTrashed(true);
          
          if (textContent && textContent.trim().length > 0) {
            console.log(`✅ HTML変換成功: ${textContent.length}文字`);
            return textContent;
          }
        }
        
        // HTML取得失敗の場合、プレーンテキストで試行
        const textResponse = UrlFetchApp.fetch(
          `https://www.googleapis.com/drive/v3/files/${docsId}/export?mimeType=text/plain`,
          {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${token}`
            },
            muteHttpExceptions: true
          }
        );
        
        if (textResponse.getResponseCode() === 200) {
          const textContent = textResponse.getContentText();
          
          // Google Docsファイルを削除
          DriveApp.getFileById(docsId).setTrashed(true);
          
          if (textContent && textContent.trim().length > 0) {
            console.log(`✅ テキスト変換成功: ${textContent.length}文字`);
            return textContent;
          }
        }
        
        // Google Docsファイルを削除（エラー時も）
        DriveApp.getFileById(docsId).setTrashed(true);
        
      } catch (exportError) {
        console.error('Google Docs export エラー:', exportError);
        
        // Google Docsファイルを削除（エラー時も）
        try {
          DriveApp.getFileById(docsId).setTrashed(true);
        } catch (deleteError) {
          console.error('Google Docs削除エラー:', deleteError);
        }
        
        throw exportError;
      }
    }
    
    throw new Error('Google Docs変換に失敗しました');
    
  } catch (error) {
    console.error('方法1失敗:', error);
    
    // 方法2: 基本的なファイル情報を取得して代替手段を提供
    try {
      console.log(`📄 方法2: ファイル情報による代替手段`);
      
      const file = DriveApp.getFileById(fileId);
      const fileInfo = {
        name: file.getName(),
        size: file.getSize(),
        lastUpdated: file.getLastUpdated(),
        description: file.getDescription() || ''
      };
      
      // ファイル情報から簡易的な情報を抽出
      let extractedInfo = `ファイル名: ${fileInfo.name}\n`;
      if (fileInfo.description) {
        extractedInfo += `説明: ${fileInfo.description}\n`;
      }
      extractedInfo += `更新日: ${fileInfo.lastUpdated}\n`;
      
      console.log(`ℹ️ ファイル情報抽出: ${extractedInfo.length}文字`);
      
      // 最低限のテキストとして返す
      return extractedInfo + '\n[注意: Wordファイルの内容は完全に抽出できませんでした。手動でテキストをコピーして再投稿してください。]';
      
    } catch (infoError) {
      console.error('方法2失敗:', infoError);
      throw new Error('すべての抽出方法が失敗しました');
    }
  }
}

/**
 * HTMLからテキストを抽出（HTMLタグを除去）
 * @param {string} html - HTML文字列
 * @return {string} - 抽出されたテキスト
 */
function extractTextFromHTML(html) {
  if (!html) return '';
  
  // HTMLタグを除去
  let text = html.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '');
  text = text.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');
  text = text.replace(/<[^>]+>/g, ' ');
  
  // HTMLエンティティをデコード
  text = text.replace(/&nbsp;/g, ' ');
  text = text.replace(/&amp;/g, '&');
  text = text.replace(/&lt;/g, '<');
  text = text.replace(/&gt;/g, '>');
  text = text.replace(/&quot;/g, '"');
  text = text.replace(/&#39;/g, "'");
  
  // 連続する空白を単一のスペースに置換
  text = text.replace(/\s+/g, ' ');
  
  return text.trim();
}

// ===================================================================
// PowerPointファイル読み取り機能
// ===================================================================

/**
 * SlackイベントからPowerPointファイル情報を抽出
 * @param {object} event - Slackイベント
 * @return {Array} - PowerPointファイル情報の配列
 */
function extractPowerPointFilesFromSlackEvent(event) {
  if (event.files && event.files.length > 0) {
    return event.files.filter(file => 
      (file.mimetype === 'application/vnd.openxmlformats-officedocument.presentationml.presentation' || 
       file.filetype === 'pptx') && 
      file.size < 50 * 1024 * 1024 // 50MB制限
    );
  }
  return [];
}

/**
 * Drive API基本機能のみを使用してPowerPointファイルからテキストを抽出
 * @param {Uint8Array} pptxData - .pptxファイルのバイナリデータ
 * @param {string} fileName - ファイル名
 * @return {string} - 抽出されたテキスト
 */
function extractTextFromPptxBasicDrive(pptxData, fileName) {
  let tempFileId = null;
  
  try {
    console.log(`📊 PowerPoint処理開始（基本Drive API使用): ${fileName}`);
    
    // 1. 一時的にDriveにアップロード
    const blob = Utilities.newBlob(pptxData, 'application/vnd.openxmlformats-officedocument.presentationml.presentation', fileName);
    const tempFile = DriveApp.createFile(blob);
    tempFileId = tempFile.getId();
    
    console.log(`📤 一時ファイル作成成功: ${tempFileId}`);
    
    // 2. Google Slidesとしてコピーしてテキストを抽出
    const extractedText = extractTextFromUploadedPptx(tempFileId, fileName);
    
    if (!extractedText || extractedText.trim().length === 0) {
      throw new Error('PowerPointファイルからテキストを抽出できませんでした');
    }
    
    console.log(`✅ テキスト抽出完了: ${extractedText.length}文字`);
    return extractedText;
    
  } catch (error) {
    console.error('PowerPoint処理エラー:', error);
    throw new Error(`PowerPointファイルからのテキスト抽出に失敗しました: ${error.message}`);
  } finally {
    // 3. 一時ファイルを削除
    if (tempFileId) {
      try {
        DriveApp.getFileById(tempFileId).setTrashed(true);
        console.log(`🗑️ 一時ファイル削除完了: ${tempFileId}`);
      } catch (deleteError) {
        console.error('一時ファイル削除エラー:', deleteError);
      }
    }
  }
}

/**
 * アップロードされたPowerPointファイルからテキストを抽出
 * @param {string} fileId - DriveファイルID
 * @param {string} fileName - ファイル名
 * @return {string} - 抽出されたテキスト
 */
function extractTextFromUploadedPptx(fileId, fileName) {
  try {
    console.log(`📊 Google Slides変換によるテキスト抽出を試行`);
    
    // Google Slidesとしてコピー
    const copyRequest = {
      'name': `temp_slides_conversion_${new Date().getTime()}`,
      'parents': [DriveApp.getRootFolder().getId()],
      'mimeType': 'application/vnd.google-apps.presentation'
    };
    
    const token = ScriptApp.getOAuthToken();
    
    // Drive APIでGoogle Slidesとしてコピー
    const copyResponse = UrlFetchApp.fetch(
      `https://www.googleapis.com/drive/v3/files/${fileId}/copy`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        payload: JSON.stringify(copyRequest),
        muteHttpExceptions: true
      }
    );
    
    if (copyResponse.getResponseCode() === 200) {
      const copyResult = JSON.parse(copyResponse.getContentText());
      const slidesId = copyResult.id;
      
      console.log(`📋 Google Slides作成成功: ${slidesId}`);
      
      try {
        // Google SlidesからHTML形式で取得
        const htmlResponse = UrlFetchApp.fetch(
          `https://www.googleapis.com/drive/v3/files/${slidesId}/export?mimeType=text/html`,
          {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${token}`
            },
            muteHttpExceptions: true
          }
        );
        
        if (htmlResponse.getResponseCode() === 200) {
          const htmlContent = htmlResponse.getContentText();
          const textContent = extractTextFromHTML(htmlContent);
          
          // Google Slidesファイルを削除
          DriveApp.getFileById(slidesId).setTrashed(true);
          
          if (textContent && textContent.trim().length > 0) {
            console.log(`✅ HTML変換成功: ${textContent.length}文字`);
            return textContent;
          }
        }
        
        // HTML取得失敗の場合、プレーンテキストで試行
        const textResponse = UrlFetchApp.fetch(
          `https://www.googleapis.com/drive/v3/files/${slidesId}/export?mimeType=text/plain`,
          {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${token}`
            },
            muteHttpExceptions: true
          }
        );
        
        if (textResponse.getResponseCode() === 200) {
          const textContent = textResponse.getContentText();
          
          // Google Slidesファイルを削除
          DriveApp.getFileById(slidesId).setTrashed(true);
          
          if (textContent && textContent.trim().length > 0) {
            console.log(`✅ テキスト変換成功: ${textContent.length}文字`);
            return textContent;
          }
        }
        
        // Google Slidesファイルを削除（エラー時も）
        DriveApp.getFileById(slidesId).setTrashed(true);
        
      } catch (exportError) {
        console.error('Google Slides export エラー:', exportError);
        
        // Google Slidesファイルを削除（エラー時も）
        try {
          DriveApp.getFileById(slidesId).setTrashed(true);
        } catch (deleteError) {
          console.error('Google Slides削除エラー:', deleteError);
        }
        
        throw exportError;
      }
    }
    
    throw new Error('Google Slides変換に失敗しました');
    
  } catch (error) {
    console.error('PowerPoint変換失敗:', error);
    
    // 代替手段: ファイル情報による代替手段
    try {
      console.log(`📊 ファイル情報による代替手段`);
      
      const file = DriveApp.getFileById(fileId);
      const fileInfo = {
        name: file.getName(),
        size: file.getSize(),
        lastUpdated: file.getLastUpdated(),
        description: file.getDescription() || ''
      };
      
      // ファイル情報から簡易的な情報を抽出
      let extractedInfo = `ファイル名: ${fileInfo.name}\n`;
      if (fileInfo.description) {
        extractedInfo += `説明: ${fileInfo.description}\n`;
      }
      extractedInfo += `更新日: ${fileInfo.lastUpdated}\n`;
      
      console.log(`ℹ️ ファイル情報抽出: ${extractedInfo.length}文字`);
      
      // 最低限のテキストとして返す
      return extractedInfo + '\n[注意: PowerPointファイルの内容は完全に抽出できませんでした。手動でテキストをコピーして再投稿してください。]';
      
    } catch (infoError) {
      console.error('ファイル情報取得失敗:', infoError);
      throw new Error('すべての抽出方法が失敗しました');
    }
  }
}

/**
 * SlackからPowerPointファイルをダウンロード
 * @param {object} fileInfo - Slackファイル情報
 * @return {Uint8Array} - PowerPointバイナリデータ
 */
function downloadPowerPointFromSlack(fileInfo) {
  try {
    console.log(`📥 Slack PowerPointファイルダウンロード開始: ${fileInfo.name}`);
    console.log(`ファイル情報: サイズ=${fileInfo.size}, MIME=${fileInfo.mimetype}`);
    
    const response = UrlFetchApp.fetch(fileInfo.url_private, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${CONFIG.SLACK_BOT_TOKEN}`,
        'User-Agent': 'CalendarBot/1.0'
      },
      muteHttpExceptions: true,
      followRedirects: true
    });
    
    const responseCode = response.getResponseCode();
    console.log(`ダウンロード応答コード: ${responseCode}`);
    
    if (responseCode === 200) {
      const blob = response.getBlob();
      const downloadedData = blob.getBytes();
      
      console.log(`✅ PowerPointダウンロード成功: ${downloadedData.length} bytes`);
      
      // .pptxヘッダーの確認（PKアーカイブ形式）
      console.log(`PowerPointヘッダー: ${Array.from(downloadedData.slice(0, 4)).map(b => b.toString(16)).join(' ')}`);
      
      // .pptxファイルはZIPアーカイブなので、'PK'で始まる
      if (downloadedData[0] !== 0x50 || downloadedData[1] !== 0x4B) {
        console.warn(`⚠️ 無効なPowerPointヘッダー検出`);
        // ただし、処理は続行（Slackが変換している可能性があるため）
      }
      
      return downloadedData;
    } else {
      const errorBody = response.getContentText();
      console.error(`PowerPointダウンロード失敗: ${responseCode}`);
      console.error(`エラー詳細: ${errorBody}`);
      throw new Error(`Slack PowerPointファイルダウンロード失敗: ${responseCode} - ${errorBody}`);
    }
  } catch (error) {
    console.error('Slack PowerPointファイルダウンロードエラー:', error);
    throw new Error(`Slackからのファイルダウンロードに失敗しました: ${error.message}`);
  }
}

/**
 * PowerPoint由来の単一予定追加成功メッセージを作成します
 * @param {object} event - 作成されたイベント
 * @param {string} userId - ユーザーID
 * @param {string} sourceFile - 元のPowerPointファイル名
 * @return {object} - Slackメッセージ用のBlock Kitオブジェクト
 */
function createPowerPointScheduleSuccessMessage(event, userId, sourceFile) {
  let timeText = '';
  if (event.isAllDay) {
    if (event.endDate && event.endDate !== Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'yyyy-MM-dd')) {
      const startDateFormatted = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      const endDateFormatted = Utilities.formatDate(new Date(event.endDate), 'Asia/Tokyo', 'M月d日(E)');
      const days = Math.ceil((new Date(event.endDate) - event.startTime) / (1000 * 60 * 60 * 24)) + 1;
      timeText = `*🗓️ 期間:* ${startDateFormatted} 〜 ${endDateFormatted}（${days}日間・終日）`;
    } else {
      const eventDate = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      timeText = `*🗓️ 日付:* ${eventDate}（終日）`;
    }
  } else {
    const startTime = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E) HH:mm');
    const endTime = Utilities.formatDate(event.endTime, 'Asia/Tokyo', 'HH:mm');
    timeText = `*🕐 日時:* ${startTime} 〜 ${endTime}`;
  }

  let locationText = '';
  if (event.location) {
    locationText = `\n*📍 場所:* ${event.location}`;
  }

  const blocks = [{
    type: 'section',
    text: { type: 'mrkdwn', text: `<@${userId}> ✅ PowerPointファイルから予定を追加しました！\n\n*📅 予定名:* ${event.title}\n${timeText}${locationText}\n*📊 情報源:* ${sourceFile}` }
  }, {
    type: 'actions', 
    elements: [{
      type: 'button', 
      text: { type: 'plain_text', text: 'カレンダーで確認' },
      action_id: 'open_calendar',
      style: 'primary',
      value: JSON.stringify({ 
        action: 'open_calendar', 
        url: event.htmlLink || 'https://calendar.google.com/calendar',
        eventTitle: event.title 
      })
    }]
  }];
  return { blocks: blocks };
}

// ===================================================================
// PDF読み取り機能
// ===================================================================

/**
 * PDFファイルをCloud Storageにアップロード
 * @param {Uint8Array} pdfData - PDFファイルのバイナリデータ
 * @param {string} fileName - ファイル名
 * @return {string} - GCS URI
 */
function uploadPDFToGCS(pdfData, fileName) {
  const timestamp = new Date().getTime();
  const gcsFileName = `pdfs/${timestamp}_${fileName}`;
  
  try {
    console.log(`GCSアップロード開始: ${gcsFileName}`);
    
    const response = UrlFetchApp.fetch(
      `https://storage.googleapis.com/upload/storage/v1/b/${CONFIG.GCS_BUCKET_NAME}/o?uploadType=media&name=${encodeURIComponent(gcsFileName)}`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${ScriptApp.getOAuthToken()}`,
          'Content-Type': 'application/pdf'
        },
        payload: pdfData,
        muteHttpExceptions: true
      }
    );
    
    const responseCode = response.getResponseCode();
    console.log(`GCSレスポンス: ${responseCode}`);
    
    if (responseCode === 200) {
      console.log(`✅ GCSアップロード成功: ${gcsFileName}`);
      return `gs://${CONFIG.GCS_BUCKET_NAME}/${gcsFileName}`;
    } else {
      const errorResponse = response.getContentText();
      console.error(`GCSアップロード失敗: ${responseCode}`);
      console.error(`エラーレスポンス: ${errorResponse}`);
      throw new Error(`GCSアップロード失敗: ${responseCode} - ${errorResponse}`);
    }
  } catch (error) {
    console.error('GCSアップロードエラー:', error);
    throw new Error(`Cloud Storageへのアップロードに失敗しました: ${error.message}`);
  }
}

/**
 * Vision APIでPDF処理を開始
 * @param {string} gcsSourceUri - GCS URI
 * @param {string} fileName - ファイル名（結果保存用）
 * @return {string} - オペレーション名
 */
function startPDFProcessing(gcsSourceUri, fileName) {
  const outputUri = `gs://${CONFIG.GCS_BUCKET_NAME}/results/${fileName}_${new Date().getTime()}/`;
  
  const request = {
    requests: [{
      inputConfig: {
        gcsSource: { uri: gcsSourceUri },
        mimeType: 'application/pdf'
      },
      features: [{ type: 'DOCUMENT_TEXT_DETECTION' }],
      outputConfig: {
        gcsDestination: { uri: outputUri },
        batchSize: 10
      }
    }]
  };
  
  try {
    const apiUrl = 'https://vision.googleapis.com/v1/files:asyncBatchAnnotate';
    
    const headers = {
      'Authorization': `Bearer ${ScriptApp.getOAuthToken()}`,
      'Content-Type': 'application/json'
    };
    
    const response = UrlFetchApp.fetch(apiUrl, {
      method: 'POST',
      headers: headers,
      payload: JSON.stringify(request)
    });
    
    if (response.getResponseCode() === 200) {
      const result = JSON.parse(response.getContentText());
      return result.name;
    } else {
      throw new Error(`Vision API呼び出し失敗: ${response.getResponseCode()}`);
    }
  } catch (error) {
    console.error('Vision API呼び出しエラー:', error);
    throw new Error(`Vision APIでの処理開始に失敗しました: ${error.message}`);
  }
}

function waitForProcessingComplete(operationName) {
  const maxRetries = 30;
  const retryInterval = 10000;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      const apiUrl = `https://vision.googleapis.com/v1/${operationName}`;
      
      const headers = {
        'Authorization': `Bearer ${ScriptApp.getOAuthToken()}`
      };
      
      const response = UrlFetchApp.fetch(apiUrl, { headers: headers });
      
      if (response.getResponseCode() === 200) {
        const operation = JSON.parse(response.getContentText());
        
        if (operation.done) {
          if (operation.error) {
            throw new Error(`処理エラー: ${JSON.stringify(operation.error)}`);
          }
          return operation.response;
        }
      }
      
      console.log(`処理中... ${i + 1}/${maxRetries}`);
      Utilities.sleep(retryInterval);
    } catch (error) {
      console.error(`処理状況確認エラー (${i + 1}/${maxRetries}):`, error);
      if (i === maxRetries - 1) {
        throw error;
      }
      Utilities.sleep(retryInterval);
    }
  }
  
  throw new Error('PDF処理がタイムアウトしました');
}

/**
 * 処理結果からテキストを抽出（GCS結果読み取り対応版）
 * @param {object} visionResponse - Vision APIのレスポンス
 * @return {string} - 抽出されたテキスト
 */
function getProcessingResult(visionResponse) {
  let fullText = '';
  
  try {
    console.log('🔍 Vision APIレスポンス詳細解析開始...');
    
    if (!visionResponse || !visionResponse.responses || visionResponse.responses.length === 0) {
      throw new Error('Vision APIレスポンスが無効です');
    }
    
    // 非同期処理の結果はGCSに保存されているかチェック
    const response = visionResponse.responses[0];
    
    if (response.outputConfig && response.outputConfig.gcsDestination) {
      // GCSから結果を読み取る
      const outputUri = response.outputConfig.gcsDestination.uri;
      console.log(`📂 GCS結果読み取り開始: ${outputUri}`);
      
      fullText = readResultFromGCS(outputUri);
      
      if (fullText.trim().length > 0) {
        console.log(`✅ GCSから結果読み取り成功: ${fullText.trim().length}文字`);
        return fullText.trim();
      }
    }
    
    // 従来の方法も試行（同期処理の場合）
    visionResponse.responses.forEach((response, index) => {
      console.log(`--- レスポンス ${index + 1} ---`);
      
      if (response.error) {
        console.log('❌ レスポンスエラー:', JSON.stringify(response.error, null, 2));
        return;
      }
      
      if (response.fullTextAnnotation && response.fullTextAnnotation.text) {
        console.log(`✅ 直接テキスト見つかりました (${response.fullTextAnnotation.text.length}文字)`);
        fullText += response.fullTextAnnotation.text + '\n';
      }
      
      // textAnnotationsからも試行
      if (response.textAnnotations && response.textAnnotations.length > 0) {
        console.log(`📝 textAnnotations発見: ${response.textAnnotations.length}件`);
        const allTexts = response.textAnnotations.map(annotation => annotation.description).join(' ');
        if (allTexts.trim()) {
          fullText += allTexts + '\n';
        }
      }
    });
    
    if (fullText.trim().length === 0) {
      throw new Error('PDFからテキストを抽出できませんでした');
    }
    
    return fullText.trim();
    
  } catch (error) {
    console.error('テキスト抽出エラー:', error);
    throw new Error(`テキスト抽出に失敗しました: ${error.message}`);
  }
}

/**
 * GCSから結果ファイルを読み取る（動的ファイル名対応版）
 * @param {string} outputUri - GCS出力パス
 * @return {string} - 抽出されたテキスト
 */
function readResultFromGCS(outputUri) {
  try {
    console.log(`📖 GCS結果読み取り: ${outputUri}`);
    
    // GCS URIからバケット名とパスを抽出
    const bucketName = outputUri.match(/gs:\/\/([^\/]+)/)[1];
    const dirPath = outputUri.replace(`gs://${bucketName}/`, '').replace(/\/$/, '');
    
    console.log(`バケット: ${bucketName}, ディレクトリ: ${dirPath}`);
    
    // ディレクトリ内のファイル一覧を取得
    const listResponse = UrlFetchApp.fetch(
      `https://storage.googleapis.com/storage/v1/b/${bucketName}/o?prefix=${encodeURIComponent(dirPath)}/`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${ScriptApp.getOAuthToken()}`
        },
        muteHttpExceptions: true
      }
    );
    
    if (listResponse.getResponseCode() !== 200) {
      throw new Error(`ファイル一覧取得失敗: ${listResponse.getResponseCode()} - ${listResponse.getContentText()}`);
    }
    
    const listData = JSON.parse(listResponse.getContentText());
    console.log('📁 ディレクトリ内ファイル一覧:');
    
    if (!listData.items || listData.items.length === 0) {
      throw new Error('結果ディレクトリが空です');
    }
    
    // output-*.jsonファイルを探す
    let outputFiles = [];
    listData.items.forEach(item => {
      console.log(`  ファイル: ${item.name}`);
      if (item.name.includes('output-') && item.name.endsWith('.json')) {
        outputFiles.push(item.name);
      }
    });
    
    if (outputFiles.length === 0) {
      throw new Error('output-*.jsonファイルが見つかりません');
    }
    
    console.log(`✅ 出力ファイル発見: ${outputFiles.join(', ')}`);
    
    // 全ての出力ファイルからテキストを抽出
    let allText = '';
    for (const fileName of outputFiles) {
      console.log(`📄 ファイル読み取り: ${fileName}`);
      
      const fileResponse = UrlFetchApp.fetch(
        `https://storage.googleapis.com/storage/v1/b/${bucketName}/o/${encodeURIComponent(fileName)}?alt=media`,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${ScriptApp.getOAuthToken()}`
          },
          muteHttpExceptions: true
        }
      );
      
      if (fileResponse.getResponseCode() === 200) {
        const resultData = JSON.parse(fileResponse.getContentText());
        console.log(`✅ ${fileName} 読み取り成功`);
        
        const extractedText = extractTextFromResultData(resultData);
        if (extractedText.trim()) {
          allText += extractedText + '\n';
        }
      } else {
        console.log(`❌ ${fileName} 読み取り失敗: ${fileResponse.getResponseCode()}`);
      }
    }
    
    return allText.trim();
    
  } catch (error) {
    console.error('GCS結果読み取りエラー:', error);
    throw new Error(`GCS結果読み取りに失敗しました: ${error.message}`);
  }
}

/**
 * 結果データからテキストを抽出
 * @param {object} resultData - GCSから読み取った結果データ
 * @return {string} - 抽出されたテキスト
 */
function extractTextFromResultData(resultData) {
  let fullText = '';
  
  try {
    if (resultData.responses && resultData.responses.length > 0) {
      resultData.responses.forEach((response, index) => {
        console.log(`=== 結果レスポンス ${index + 1} ===`);
        
        if (response.fullTextAnnotation && response.fullTextAnnotation.text) {
          console.log(`✅ テキスト発見: ${response.fullTextAnnotation.text.length}文字`);
          fullText += response.fullTextAnnotation.text + '\n';
        }
        
        if (response.textAnnotations && response.textAnnotations.length > 0) {
          console.log(`📝 textAnnotations: ${response.textAnnotations.length}件`);
          // 最初のtextAnnotationには全体テキストが含まれることが多い
          if (response.textAnnotations[0] && response.textAnnotations[0].description) {
            fullText += response.textAnnotations[0].description + '\n';
          }
        }
      });
    }
    
    if (fullText.trim().length === 0) {
      console.log('⚠️ 結果データにテキストが見つかりません');
    }
    
    return fullText.trim();
    
  } catch (error) {
    console.error('結果データ解析エラー:', error);
    throw new Error(`結果データ解析に失敗しました: ${error.message}`);
  }
}

/**
 * PDFからテキストを抽出するメイン関数（デバッグ強化版）
 * @param {Uint8Array} pdfData - PDFファイルのバイナリデータ
 * @param {string} fileName - ファイル名
 * @return {string} - 抽出されたテキスト
 */
function extractTextFromPDF(pdfData, fileName) {
  try {
    console.log(`📄 PDF処理開始: ${fileName}, サイズ: ${pdfData.length} bytes`);
    
    // 1. PDFデータの整合性チェック
    const validation = validatePDFData(pdfData, fileName);
    if (!validation.isValid) {
      throw new Error(`PDF検証失敗: ${validation.errorMessage}`);
    }
    
    // 2. Vision API での処理
    const gcsUri = uploadPDFToGCS(pdfData, fileName);
    console.log(`✅ GCSアップロード完了: ${gcsUri}`);
    
    const operationName = startPDFProcessing(gcsUri, fileName);
    console.log(`✅ Vision API処理開始: ${operationName}`);
    
    const result = waitForProcessingComplete(operationName);
    console.log('✅ Vision API処理完了');
    
    const extractedText = getProcessingResult(result);
    console.log(`✅ テキスト抽出完了: ${extractedText.length}文字`);
    
    return extractedText;
    
  } catch (error) {
    console.error('PDF処理エラー:', error);
    console.error('エラースタック:', error.stack);
    throw new Error(`PDFからのテキスト抽出に失敗しました: ${error.message}`);
  }
}

/**
 * SlackからPDFファイルをダウンロード（改善版）
 * @param {object} fileInfo - Slackファイル情報
 * @return {Uint8Array} - PDFバイナリデータ
 */
function downloadPDFFromSlack(fileInfo) {
  try {
    console.log(`📥 Slackファイルダウンロード開始: ${fileInfo.name}`);
    console.log(`ファイル情報: サイズ=${fileInfo.size}, MIME=${fileInfo.mimetype}`);
    console.log(`ダウンロードURL: ${fileInfo.url_private}`);
    
    const response = UrlFetchApp.fetch(fileInfo.url_private, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${CONFIG.SLACK_BOT_TOKEN}`,
        'User-Agent': 'CalendarBot/1.0'
      },
      muteHttpExceptions: true,
      followRedirects: true
    });
    
    const responseCode = response.getResponseCode();
    console.log(`ダウンロード応答コード: ${responseCode}`);
    
    if (responseCode === 200) {
      const blob = response.getBlob();
      const downloadedData = blob.getBytes();
      
      console.log(`✅ ダウンロード成功: ${downloadedData.length} bytes`);
      console.log(`元ファイルサイズ: ${fileInfo.size} bytes`);
      
      // サイズの整合性確認
      if (downloadedData.length !== fileInfo.size) {
        console.warn(`⚠️ ファイルサイズ不一致: 期待=${fileInfo.size}, 実際=${downloadedData.length}`);
      }
      
      // PDFヘッダーの確認
      const header = String.fromCharCode.apply(null, downloadedData.slice(0, 8));
      console.log(`PDFヘッダー: ${header}`);
      
      if (!header.startsWith('%PDF-')) {
        throw new Error(`無効なPDFヘッダー: ${header}`);
      }
      
      return downloadedData;
    } else {
      const errorBody = response.getContentText();
      console.error(`ダウンロード失敗: ${responseCode}`);
      console.error(`エラー詳細: ${errorBody}`);
      throw new Error(`Slackファイルダウンロード失敗: ${responseCode} - ${errorBody}`);
    }
  } catch (error) {
    console.error('Slackファイルダウンロードエラー:', error);
    throw new Error(`Slackからのファイルダウンロードに失敗しました: ${error.message}`);
  }
}

/**
 * PDFファイルの整合性をチェック
 * @param {Uint8Array} pdfData - PDFバイナリデータ
 * @param {string} fileName - ファイル名
 * @return {object} - チェック結果
 */
function validatePDFData(pdfData, fileName) {
  const result = {
    isValid: false,
    size: pdfData.length,
    hasValidHeader: false,
    version: 'unknown',
    hasTrailer: false,
    errorMessage: null
  };
  
  try {
    // PDFヘッダーの確認
    const header = String.fromCharCode.apply(null, pdfData.slice(0, 8));
    result.hasValidHeader = header.startsWith('%PDF-');
    
    if (result.hasValidHeader) {
      result.version = header.substring(5, 8);
    }
    
    // PDFトレーラーの確認（末尾）
    const trailer = String.fromCharCode.apply(null, pdfData.slice(-32));
    result.hasTrailer = trailer.includes('%%EOF');
    
    // 基本的な暗号化チェック
    const sampleText = String.fromCharCode.apply(null, pdfData.slice(0, Math.min(2048, pdfData.length)));
    const isEncrypted = sampleText.includes('/Encrypt');
    
    result.isValid = result.hasValidHeader && result.hasTrailer && !isEncrypted;
    
    if (isEncrypted) {
      result.errorMessage = 'PDFが暗号化されています';
    } else if (!result.hasValidHeader) {
      result.errorMessage = 'PDFヘッダーが無効です';
    } else if (!result.hasTrailer) {
      result.errorMessage = 'PDFトレーラーが見つかりません（ファイルが不完全な可能性）';
    }
    
    console.log(`PDF検証結果 (${fileName}):`, result);
    return result;
    
  } catch (error) {
    result.errorMessage = `PDF検証エラー: ${error.message}`;
    console.error('PDF検証エラー:', error);
    return result;
  }
}

/**
 * Slackイベントからファイル情報を抽出
 * @param {object} event - Slackイベント
 * @return {Array} - PDFファイル情報の配列
 */
function extractPDFsFromSlackEvent(event) {
  if (event.files && event.files.length > 0) {
    return event.files.filter(file => 
      file.mimetype === 'application/pdf' && 
      file.size < 50 * 1024 * 1024 // 50MB制限
    );
  }
  return [];
}

/**
 * PDF由来の複数予定の確認メッセージを送信します（安全版）
 */
function sendMultiplePDFScheduleConfirmationSafe(channel, user, scheduleDataArray, sourceFile) {
  try {
    console.log(`📝 複数予定メッセージ作成開始: ${scheduleDataArray.length}件`);
    
    // タイトルを安全な長さに制限
    const safeScheduleData = scheduleDataArray.map((schedule, index) => {
      const safeTitle = schedule.title.length > 50 ? 
        schedule.title.substring(0, 47) + '...' : schedule.title;
      
      console.log(`予定${index + 1} タイトル処理: ${schedule.title.length}文字 → ${safeTitle.length}文字`);
      
      return {
        ...schedule,
        title: safeTitle
      };
    });
    
    const blocks = [{
      type: 'section',
      text: { 
        type: 'mrkdwn', 
        text: `<@${user}> 📄 PDFから${safeScheduleData.length}件の予定を検出しました！` 
      }
    }, {
      type: 'context',
      elements: [{ 
        type: 'mrkdwn', 
        text: `📄 情報源: ${sourceFile}` 
      }]
    }, {
      type: 'divider'
    }];

    // 各予定を表示（最大3件まで）- 安全性を優先
    const displayCount = Math.min(safeScheduleData.length, 3);
    console.log(`📋 表示する予定数: ${displayCount}件`);
    
    for (let i = 0; i < displayCount; i++) {
      const schedule = safeScheduleData[i];
      console.log(`📋 予定${i + 1}の表示データ作成中...`);
      
      try {
        const { title, date, endDate, startTime, endTime, isAllDay, location } = schedule;
        
        let timeText = '';
        if (isAllDay) {
          if (endDate && endDate !== date) {
            const startDateFormatted = Utilities.formatDate(new Date(date), 'Asia/Tokyo', 'M月d日');
            const endDateFormatted = Utilities.formatDate(new Date(endDate), 'Asia/Tokyo', 'M月d日');
            timeText = `${startDateFormatted}〜${endDateFormatted}（終日）`;
          } else {
            const eventDate = Utilities.formatDate(new Date(date), 'Asia/Tokyo', 'M月d日');
            timeText = `${eventDate}（終日）`;
          }
        } else {
          const eventDate = Utilities.formatDate(new Date(date), 'Asia/Tokyo', 'M月d日');
          const start = startTime || '時間未定';
          const end = endTime || '';
          timeText = end ? `${eventDate} ${start}〜${end}` : `${eventDate} ${start}〜`;
        }
        
        let locationInfo = location ? ` 📍${location.substring(0, 20)}` : '';
        
        const value = { 
          action: 'add_from_pdf', 
          eventData: schedule 
        };
        
        blocks.push({
          type: 'section',
          text: { 
            type: 'mrkdwn', 
            text: `*${i + 1}️⃣ ${title}*\n${timeText}${locationInfo}` 
          },
          accessory: {
            type: 'button',
            text: { type: 'plain_text', text: '追加' },
            style: 'primary',
            action_id: 'confirm_add_from_pdf',
            value: JSON.stringify(value)
          }
        });
        
        console.log(`✅ 予定${i + 1}の表示データ作成完了`);
      } catch (scheduleError) {
        console.error(`❌ 予定${i + 1}の表示データ作成エラー:`, scheduleError);
        // この予定をスキップして続行
        continue;
      }
    }

    // 一括追加ボタン
    console.log(`📝 一括追加ボタン作成中...`);
    try {
      const allSchedulesValue = {
        action: 'add_all_from_pdf',
        eventDataArray: scheduleDataArray // 元の完全なデータを使用
      };
      
      blocks.push({
        type: 'actions',
        elements: [{
          type: 'button',
          text: { type: 'plain_text', text: '✅ すべて追加' },
          style: 'primary',
          action_id: 'confirm_add_all_from_pdf',
          value: JSON.stringify(allSchedulesValue)
        }, {
          type: 'button',
          text: { type: 'plain_text', text: '❌ キャンセル' },
          action_id: 'cancel_action'
        }]
      });
      
      console.log(`✅ 一括追加ボタン作成完了`);
    } catch (buttonError) {
      console.error(`❌ 一括追加ボタン作成エラー:`, buttonError);
    }

    console.log(`📤 Slackメッセージ送信中... (${blocks.length}ブロック)`);
    
    // メッセージサイズをチェック
    const messageSize = JSON.stringify(blocks).length;
    console.log(`📏 メッセージサイズ: ${messageSize} 文字`);
    
    if (messageSize > 40000) {
      throw new Error(`メッセージが大きすぎます: ${messageSize}文字`);
    }
    
    sendSlackMessage(channel, 'PDFから複数の予定を検出しました。', null, { blocks: blocks });
    console.log(`✅ Slackメッセージ送信完了`);
    
  } catch (error) {
    console.error('❌ 複数予定確認メッセージ送信エラー:', error);
    console.error('エラースタック:', error.stack);
    
    // 最終フォールバック: 非常にシンプルなメッセージ
    const fallbackMessage = `✅ PDFから${scheduleDataArray.length}件の予定を検出しました！\n\n` +
      scheduleDataArray.slice(0, 3).map((schedule, index) => {
        const shortTitle = schedule.title.substring(0, 30);
        const date = Utilities.formatDate(new Date(schedule.date), 'Asia/Tokyo', 'M/d');
        return `${index + 1}. ${shortTitle}... (${date})`;
      }).join('\n') +
      (scheduleDataArray.length > 3 ? `\n...他${scheduleDataArray.length - 3}件` : '') +
      `\n\n手動で予定を追加してください。`;
    
    sendSlackMessage(channel, fallbackMessage, user);
  }
}

/**
 * PDF由来の単一予定追加成功メッセージを作成します（カレンダーボタン改善版）
 */
function createPDFScheduleSuccessMessage(event, userId, sourceFile) {
  let timeText = '';
  if (event.isAllDay) {
    if (event.endDate && event.endDate !== Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'yyyy-MM-dd')) {
      const startDateFormatted = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      const endDateFormatted = Utilities.formatDate(new Date(event.endDate), 'Asia/Tokyo', 'M月d日(E)');
      const days = Math.ceil((new Date(event.endDate) - event.startTime) / (1000 * 60 * 60 * 24)) + 1;
      timeText = `*🗓️ 期間:* ${startDateFormatted} 〜 ${endDateFormatted}（${days}日間・終日）`;
    } else {
      const eventDate = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      timeText = `*🗓️ 日付:* ${eventDate}（終日）`;
    }
  } else {
    const startTime = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E) HH:mm');
    const endTime = Utilities.formatDate(event.endTime, 'Asia/Tokyo', 'HH:mm');
    timeText = `*🕐 日時:* ${startTime} 〜 ${endTime}`;
  }

  let locationText = '';
  if (event.location) {
    locationText = `\n*📍 場所:* ${event.location}`;
  }

  const blocks = [{
    type: 'section',
    text: { type: 'mrkdwn', text: `<@${userId}> ✅ PDFから予定を追加しました！\n\n*📅 予定名:* ${event.title}\n${timeText}${locationText}\n*📄 情報源:* ${sourceFile}` }
  }, {
    type: 'actions', 
    elements: [{
      type: 'button', 
      text: { type: 'plain_text', text: 'カレンダーで確認' },
      action_id: 'open_calendar',
      style: 'primary',
      value: JSON.stringify({ 
        action: 'open_calendar', 
        url: event.htmlLink || 'https://calendar.google.com/calendar',
        eventTitle: event.title 
      })
    }]
  }];
  return { blocks: blocks };
}

/**
 * 複数予定追加成功メッセージを作成します（カレンダーボタン改善版）
 */
function createMultiplePDFScheduleSuccessMessage(createdEvents, failedEvents, userId, sourceFile) {
  const successCount = createdEvents.length;
  const failedCount = failedEvents.length;
  
  let headerText = `<@${userId}> ✅ PDFから${successCount}件の予定を追加しました！`;
  
  const blocks = [{
    type: 'section',
    text: { type: 'mrkdwn', text: headerText }
  }];
  
  if (sourceFile) {
    blocks.push({
      type: 'context',
      elements: [{ type: 'mrkdwn', text: `📄 情報源: ${sourceFile}` }]
    });
  }
  
  if (successCount > 0) {
    blocks.push({ type: 'divider' });
    
    createdEvents.slice(0, 5).forEach((event, index) => {
      const startTime = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M/d HH:mm');
      blocks.push({
        type: 'section',
        text: { type: 'mrkdwn', text: `${index + 1}️⃣ *${event.title}*\n>${startTime}〜` }
      });
    });
  }
  
  if (failedCount > 0) {
    blocks.push({
      type: 'section',
      text: { type: 'mrkdwn', text: `⚠️ ${failedCount}件の予定は追加に失敗しました:\n${failedEvents.join(', ')}` }
    });
  }
  
  blocks.push({
    type: 'actions', 
    elements: [{
      type: 'button', 
      text: { type: 'plain_text', text: 'カレンダーで確認' },
      action_id: 'open_calendar',
      style: 'primary',
      value: JSON.stringify({ 
        action: 'open_calendar', 
        url: 'https://calendar.google.com/calendar',
        eventTitle: `${successCount}件の予定` 
      })
    }]
  });
  
  return { blocks: blocks };
}

// ===================================================================
// URL読み取り機能
// ===================================================================

/**
 * テキストからURLを抽出します。
 * @param {string} text - 検索対象のテキスト
 * @return {Array<string>} - 抽出されたURLの配列
 */
function extractUrlsFromText(text) {
  if (!text) return [];
  
  // URL正規表現（http/https）
  const urlRegex = /https?:\/\/[^\s<>"{}|\\^`[\]]+/gi;
  const matches = text.match(urlRegex);
  
  if (!matches) return [];
  
  // 重複を除去し、有効なURLのみを返す
  const uniqueUrls = [...new Set(matches)];
  return uniqueUrls.filter(url => isValidScheduleUrl(url));
}

/**
 * 予定情報が含まれている可能性の高いURLかを判定します。
 * @param {string} url - 判定対象のURL
 * @return {boolean} - 予定情報が含まれている可能性がある場合true
 */
function isValidScheduleUrl(url) {
  if (!url) return false;
  
  // 除外するURL（画像、CSS、JSなど）
  const excludePatterns = [
    /\.(jpg|jpeg|png|gif|webp|svg|css|js|ico)$/i,
    /\/(api|static|assets|cdn)\//i,
    /(twitter\.com|facebook\.com|instagram\.com)\/(?!events)/i
  ];
  
  // 除外パターンにマッチする場合はfalse
  if (excludePatterns.some(pattern => pattern.test(url))) {
    return false;
  }
  
  // 予定関連の可能性が高いURLパターン
  const schedulePatterns = [
    /event/i, /meeting/i, /conference/i, /seminar/i,
    /workshop/i, /training/i, /session/i, /calendar/i,
    /schedule/i, /agenda/i, /program/i, /registration/i
  ];
  
  // 予定関連キーワードがある場合は優先的に処理
  if (schedulePatterns.some(pattern => pattern.test(url))) {
    return true;
  }
  
  // その他のURLも一般的には処理対象とする
  return true;
}

/**
 * WebページのHTMLコンテンツを取得します。
 * @param {string} url - 取得対象のURL
 * @return {string} - 抽出されたテキストコンテンツ
 */
function fetchWebPageContent(url) {
  try {
    console.log(`Webページ取得開始: ${url}`);
    
    const response = UrlFetchApp.fetch(url, {
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; CalendarBot/1.0)'
      },
      muteHttpExceptions: true,
      followRedirects: true
    });
    
    const responseCode = response.getResponseCode();
    if (responseCode !== 200) {
      throw new Error(`HTTP ${responseCode}: ページの取得に失敗しました`);
    }
    
    const html = response.getContentText();
    const textContent = extractTextFromHtml(html);
    
    console.log(`テキスト抽出完了: ${textContent.length}文字`);
    
    // 長すぎる場合は先頭部分のみを使用（Gemini APIの制限を考慮）
    return textContent.length > 10000 ? textContent.substring(0, 10000) + '...' : textContent;
    
  } catch (error) {
    console.error('Webページ取得エラー:', error);
    throw new Error(`Webページの取得に失敗しました: ${error.message}`);
  }
}

/**
 * HTMLからテキストコンテンツを抽出します（簡易版HTMLパーサー）。
 * @param {string} html - HTMLコンテンツ
 * @return {string} - 抽出されたテキスト
 */
function extractTextFromHtml(html) {
  if (!html) return '';
  
  // script、styleタグの内容を除去
  let text = html.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '');
  text = text.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');
  
  // HTMLタグを除去
  text = text.replace(/<[^>]+>/g, ' ');
  
  // HTMLエンティティをデコード
  text = text.replace(/&nbsp;/g, ' ');
  text = text.replace(/&amp;/g, '&');
  text = text.replace(/&lt;/g, '<');
  text = text.replace(/&gt;/g, '>');
  text = text.replace(/&quot;/g, '"');
  text = text.replace(/&#39;/g, "'");
  
  // 連続する空白を単一のスペースに置換
  text = text.replace(/\s+/g, ' ');
  
  // 前後の空白を除去
  return text.trim();
}

/**
 * WebページのテキストコンテンツからGemini APIを使って予定情報を抽出します（複数日修正版）。
 * @param {string} webContent - Webページのテキスト内容
 * @param {string} sourceUrl - 元のURL
 * @return {Array<object>} - 抽出された予定データの配列
 */
function parseScheduleFromWebContent(webContent, sourceUrl) {
  const now = new Date();
  const currentDate = Utilities.formatDate(now, 'Asia/Tokyo', 'yyyy-MM-dd HH:mm (E)');
  
  const prompt = `
現在の日時: ${currentDate}
以下のWebページの内容から、予定・イベント・会議などの情報を抽出してください。

Webページ内容:
${webContent}

元URL: ${sourceUrl}

重要なルール:
1. 期間を表す表現（「○日から○日まで」「○日〜○日」「3日間の」等）は、必ず1つのイベントとして扱う
2. 同じタイトルで複数日にわたる場合は、複数のイベントではなく1つの期間イベントとして認識する
3. 複数日イベントの場合、必ずendDateに最終日を設定する

抽出項目（予定ごとに）:
- title: 予定のタイトル
- date: 開始日 (YYYY-MM-DD形式、年が明記されていない場合は2025年と仮定)
- endDate: 終了日 (YYYY-MM-DD形式、単日の場合はnull、複数日の場合は最終日)
- startTime: 開始時間 (HH:MM形式、不明な場合はnull)
- endTime: 終了時間 (HH:MM形式、不明な場合はnull)
- isAllDay: 終日イベントか (true/false)
- location: 開催場所（オンライン、住所、会議室名など）
- description: 詳細説明
- sourceUrl: "${sourceUrl}"

期間表現の例（これらは全て1つのイベントとして扱う）：
- 「2025年4月17日〜19日 国際学術集会」→ 1つのイベント（date: "2025-04-17", endDate: "2025-04-19"）
- 「3日間のワークショップ」→ 1つのイベント（開始日から2日後をendDateに設定）

絶対にやってはいけないこと：
- 複数日の予定を複数のイベントに分割すること
- 同じタイトルで日付だけ違うイベントを複数作ること

その他のルール:
1. 予定が複数ある場合は配列で返す（ただし各予定は1つのイベントとして）
2. 日付が過去の場合は除外する
3. 明確な予定情報がない場合は空配列[]を返す
4. 時間が不明な場合はisAllDay: trueとする
5. 年が記載されていない場合は2025年と仮定
6. 「詳細は〜」「問い合わせ先〜」などの部分もdescriptionに含める

例:
[
  {
    "title": "AI技術セミナー",
    "date": "2025-02-15",
    "endDate": "2025-02-17",
    "startTime": null,
    "endTime": null,
    "isAllDay": true,
    "location": "東京国際フォーラム",
    "description": "3日間にわたる最新のAI技術動向について専門家が解説します。",
    "sourceUrl": "${sourceUrl}"
  }
]

JSON配列のみを返してください（説明や\`\`\`は不要）:`;

  try {
    const result = callGemini(prompt);
    
    // 結果が配列でない場合は配列に変換
    const scheduleArray = Array.isArray(result) ? result : (result ? [result] : []);
    
    // 有効な予定のみをフィルタリング
    const validSchedules = scheduleArray.filter(schedule => {
      return schedule && 
             schedule.title && 
             schedule.date && 
             /^\d{4}-\d{2}-\d{2}$/.test(schedule.date);
    });
    
    console.log(`${validSchedules.length}件の有効な予定を抽出しました`);
    
    // デバッグ：抽出された予定の詳細をログ出力
    validSchedules.forEach((schedule, index) => {
      if (schedule.endDate && schedule.endDate !== schedule.date) {
        console.log(`複数日イベント${index + 1}: ${schedule.title} (${schedule.date} 〜 ${schedule.endDate})`);
      } else {
        console.log(`単日イベント${index + 1}: ${schedule.title} (${schedule.date})`);
      }
    });
    
    return validSchedules;
    
  } catch (error) {
    console.error('Webコンテンツ解析エラー:', error);
    throw new Error(`予定情報の解析に失敗しました: ${error.message}`);
  }
}

/**
 * URL由来の単一予定追加成功メッセージを作成します（カレンダーボタン改善版）
 */
function createUrlScheduleSuccessMessage(event, userId, sourceUrl) {
  let timeText = '';
  if (event.isAllDay) {
    if (event.endDate && event.endDate !== Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'yyyy-MM-dd')) {
      const startDateFormatted = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      const endDateFormatted = Utilities.formatDate(new Date(event.endDate), 'Asia/Tokyo', 'M月d日(E)');
      const days = Math.ceil((new Date(event.endDate) - event.startTime) / (1000 * 60 * 60 * 24)) + 1;
      timeText = `*🗓️ 期間:* ${startDateFormatted} 〜 ${endDateFormatted}（${days}日間・終日）`;
    } else {
      const eventDate = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      timeText = `*🗓️ 日付:* ${eventDate}（終日）`;
    }
  } else {
    const startTime = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E) HH:mm');
    const endTime = Utilities.formatDate(event.endTime, 'Asia/Tokyo', 'HH:mm');
    timeText = `*🕐 日時:* ${startTime} 〜 ${endTime}`;
  }

  let locationText = '';
  if (event.location) {
    locationText = `\n*📍 場所:* ${event.location}`;
  }

  const blocks = [{
    type: 'section',
    text: { type: 'mrkdwn', text: `<@${userId}> ✅ URLから予定を追加しました！\n\n*📅 予定名:* ${event.title}\n${timeText}${locationText}\n*🔗 情報源:* ${sourceUrl}` }
  }, {
    type: 'actions', 
    elements: [{
      type: 'button', 
      text: { type: 'plain_text', text: 'カレンダーで確認' },
      action_id: 'open_calendar',
      style: 'primary',
      value: JSON.stringify({ 
        action: 'open_calendar', 
        url: event.htmlLink || 'https://calendar.google.com/calendar',
        eventTitle: event.title 
      })
    }]
  }];
  return { blocks: blocks };
}

/**
 * URL由来の複数予定追加成功メッセージを作成します（カレンダーボタン改善版）
 */
function createMultipleUrlScheduleSuccessMessage(createdEvents, failedEvents, userId, sourceUrl) {
  const successCount = createdEvents.length;
  const failedCount = failedEvents.length;
  
  let headerText = `<@${userId}> ✅ URLから${successCount}件の予定を追加しました！`;
  
  const blocks = [{
    type: 'section',
    text: { type: 'mrkdwn', text: headerText }
  }];
  
  if (sourceUrl) {
    blocks.push({
      type: 'context',
      elements: [{ type: 'mrkdwn', text: `🔗 情報源: ${sourceUrl}` }]
    });
  }
  
  if (successCount > 0) {
    blocks.push({ type: 'divider' });
    
    createdEvents.slice(0, 5).forEach((event, index) => {
      const startTime = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M/d HH:mm');
      blocks.push({
        type: 'section',
        text: { type: 'mrkdwn', text: `${index + 1}️⃣ *${event.title}*\n>${startTime}〜` }
      });
    });
  }
  
  if (failedCount > 0) {
    blocks.push({
      type: 'section',
      text: { type: 'mrkdwn', text: `⚠️ ${failedCount}件の予定は追加に失敗しました:\n${failedEvents.join(', ')}` }
    });
  }
  
  blocks.push({
    type: 'actions', 
    elements: [{
      type: 'button', 
      text: { type: 'plain_text', text: 'カレンダーで確認' },
      action_id: 'open_calendar',
      style: 'primary',
      value: JSON.stringify({ 
        action: 'open_calendar', 
        url: 'https://calendar.google.com/calendar',
        eventTitle: `${successCount}件の予定` 
      })
    }]
  });
  
  return { blocks: blocks };
}

// ===================================================================
// フロー別処理 (確認 / 追加 / 変更 / 削除)
// ===================================================================

/**
 * 予定確認のリクエストを処理します。
 * @param {object} event - Slackイベントデータ
 */
function handleCheckRequest(event) {
  try {
    const { text, channel, user } = event;
    sendSlackMessage(channel, '予定を確認しています... 🗓️', user);

    const queryDetails = parseCheckQueryWithGemini(text);
    const { startTime, endTime } = getDateRange(queryDetails.timeRange);
    
    if (!startTime || !endTime) {
      throw new Error('期間の指定を認識できませんでした。');
    }

    const searchKeywords = (queryDetails.keywords && Array.isArray(queryDetails.keywords)) ? queryDetails.keywords.join(' ') : '';
    const events = CalendarApp.getCalendarById(CONFIG.CALENDAR_ID).getEvents(startTime, endTime, { search: searchKeywords });

    const responseMessage = formatEventListMessage(events, queryDetails, user, startTime, endTime);
    sendSlackMessage(channel, null, null, responseMessage);

  } catch (error) {
    console.error('handleCheckRequest Error:', error, error.stack);
    sendSlackMessage(event.channel, `エラーが発生しました: ${error.message}`, event.user);
  }
}

// --- 予定の「追加」フロー ---
function handleScheduleRequest(event) {
  try {
    const { text, channel, user } = event;
    sendSlackMessage(channel, '予定を解析中です... ⏳', user);
    
    console.log(`予定解析開始: "${text}"`);
    const eventData = parseScheduleWithGemini(text);
    console.log(`解析結果:`, JSON.stringify(eventData, null, 2));
    
    // 複数日イベントの検証
    if (eventData.endDate && eventData.endDate !== eventData.date) {
      console.log(`複数日イベント検出: ${eventData.date} 〜 ${eventData.endDate}`);
    }
    
    // 繰り返し予定の日付処理を改善
    if (!eventData.date && eventData.recurrence) {
      const firstDate = getFirstOccurrenceDate(eventData.recurrence);
      if (firstDate) {
        eventData.date = Utilities.formatDate(firstDate, 'Asia/Tokyo', 'yyyy-MM-dd');
        console.log(`最初の該当日を計算しました: ${eventData.date} (${eventData.recurrence})`);
      } else {
        throw new Error(`繰り返しパターン「${eventData.recurrence}」の解析に失敗しました。`);
      }
    }
    
    if (!eventData.date) {
        throw new Error('予定の日付を特定できませんでした。単発の予定は「明日」や「来週月曜」のように、繰り返し予定は「毎週月曜」のように指定してください。');
    }
    
    // 直接追加せず、確認メッセージを送信
    sendAddConfirmationMessage(channel, user, eventData);
    
  } catch (error) {
    console.error('handleScheduleRequest Error:', error, error.stack);
    const errorMessage = `❌ ${error.message}\n\n💡 使用例:\n• 単発の予定: 「明日の14時から16時まで会議」\n• 繰り返し予定: 「毎週木曜日16時から放射線カンファレンス」\n• 複数日予定: 「4月17日から19日の学術集会」`;
    sendSlackMessage(event.channel, errorMessage, event.user);
  }
}

// --- 予定の「削除」フロー ---
function handleDeleteRequest(event) {
  const { text, channel, user } = event;
  sendSlackMessage(channel, '削除対象の予定を検索中です... 🔍', user);
  const searchResult = parseSearchKeywordsWithGemini(text);
  const events = findEventsByKeywords(searchResult.keywords, searchResult.dateRange);
  if (events.length === 0) {
    sendSlackMessage(channel, '該当する予定が見つかりませんでした。', user);
  } else if (events.length === 1) {
    // 検索結果の eventObject を直接使用
    const fullEvent = events[0].eventObject;
    if (fullEvent) {
      sendConfirmationMessage(channel, user, fullEvent, 'delete');
    } else {
      sendSlackMessage(channel, 'エラー: 予定の検索には成功しましたが、詳細情報の取得に失敗しました。', user);
    }
  } else {
    sendEventClarificationMessage(channel, user, events.slice(0, 5), 'delete');
  }
}

// --- 予定の「変更」フロー ---
function handleModifyRequest(event) {
    const { text, channel, user } = event;
    sendSlackMessage(channel, '変更対象の予定を検索・内容を解析中です... ✍️', user);
    const modificationDetails = parseModificationQueryWithGemini(text);
    const events = findEventsByKeywords(modificationDetails.searchKeywords, modificationDetails.dateRange);
    if (events.length === 0) {
        sendSlackMessage(channel, '該当する予定が見つかりませんでした。', user);
    } else if (events.length === 1) {
        // 検索結果の eventObject を直接使用
        const fullEvent = events[0].eventObject;
        if (fullEvent) {
          modificationDetails.targetEventId = fullEvent.getId();
          sendConfirmationMessage(channel, user, fullEvent, 'modify', modificationDetails);
        } else {
          sendSlackMessage(channel, 'エラー: 予定の検索には成功しましたが、詳細情報の取得に失敗しました。', user);
        }
    } else {
        sendEventClarificationMessage(channel, user, events.slice(0, 5), 'modify', modificationDetails);
    }
}

// ===================================================================
// Gemini API 関連 (テキスト解析) - 改善版
// ===================================================================

/**
 * 汎用的なGemini API呼び出し関数です。
 * @param {string} prompt - Geminiに送るプロンプト
 * @return {object} - 解析されたJSONオブジェクト
 */
function callGemini(prompt) {
  const requestBody = { contents: [{ parts: [{ text: prompt }] }] };
  const options = {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(requestBody),
    muteHttpExceptions: true
  };

  const modelNames = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite-preview-06-17',
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite'
  ];

  for (const modelName of modelNames) {
    const apiVersion = modelName.includes('preview') ? 'v1beta' : 'v1beta';
    const apiUrl = `https://generativelanguage.googleapis.com/${apiVersion}/models/${modelName}:generateContent?key=${CONFIG.GEMINI_API_KEY}`;
    try {
      console.log(`Trying model: ${modelName}...`);
      const response = UrlFetchApp.fetch(apiUrl, options);
      const responseCode = response.getResponseCode();
      const responseText = response.getContentText();

      if (responseCode === 200) {
        const data = JSON.parse(responseText);
        if (data.candidates && data.candidates.length > 0) {
            const generatedText = data.candidates[0].content.parts[0].text;
            const cleanJson = generatedText.replace(/```json|```/g, '').trim();
            console.log(`Successfully used model: ${modelName}`);
            return JSON.parse(cleanJson);
        }
      } else {
        if (responseCode === 429) {
          console.log(`Model ${modelName} failed due to rate limiting (429). Trying next model...`);
        } else {
          console.log(`Model ${modelName} failed with code ${responseCode}: ${responseText}`);
        }
      }
    } catch (error) {
      console.log(`Model ${modelName} error:`, error.toString());
    }
  }
  throw new Error('すべてのGeminiモデルでの解析に失敗しました。APIキーやモデル名を確認してください。');
}

/**
 * 予定「確認」のためにテキストを解析します（具体的日付対応版）。
 */
function parseCheckQueryWithGemini(text) {
  const now = new Date();
  const currentDate = Utilities.formatDate(now, 'Asia/Tokyo', 'yyyy-MM-dd (E)');
  const currentYear = now.getFullYear();
  
  const prompt = `
現在の日時: ${currentDate}
現在の年: ${currentYear}

以下のテキストから、カレンダーの予定を確認するための条件を抽出してください。

抽出項目:
- timeRange: 時間範囲を示すキーワード。以下のいずれかの形式で返してください：
  - 相対的な指定: "今日", "明日", "今週", "来週", "今月", "来月"
  - 具体的な日付: "YYYY-MM-DD" 形式（例：2025-01-15）
  - 具体的な月: "YYYY-MM" 形式（例：2025-01）
  - 年の指定がない場合は現在の年（${currentYear}）を仮定してください
  - 日付指定が全くない場合は "未来" を返してください（今日から60日後まで検索）
- keywords: 特定の予定を検索するためのキーワードを「配列」で返してください。なければnull。

重要なルール:
1. 日付の解析例：
   - "1月15日" → "2025-01-15"
   - "3月" → "2025-03"  
   - "12/25" → "2025-12-25"
   - "今月" → "今月"（相対的表現のまま）
   - "来週" → "来週"（相対的表現のまま）
   
2. 年が明記されていない場合は${currentYear}年と仮定
3. 月のみの指定（"3月"、"March"など）は"YYYY-MM"形式で返す
4. 日付に関係のない単語はkeywordsに含める

例：
- 入力: "1月15日の会議を教えて" → {"timeRange": "2025-01-15", "keywords": ["会議"]}
- 入力: "3月の予定はある？" → {"timeRange": "2025-03", "keywords": null}
- 入力: "明日のランチの予定" → {"timeRange": "明日", "keywords": ["ランチ"]}
- 入力: "来週の会議室予約状況" → {"timeRange": "来週", "keywords": ["会議室", "予約"]}
- 入力: "会議の予定を教えて" → {"timeRange": "未来", "keywords": ["会議"]}
- 入力: "定例会はいつ？" → {"timeRange": "未来", "keywords": ["定例会"]}

テキスト: "${text}"

JSON形式で回答してください：`;
  
  return callGemini(prompt);
}

/**
 * 予定「追加」のためにテキストを解析します（日付認識強化版）。
 */
function parseScheduleWithGemini(text) {
  const now = new Date();
  const currentDate = Utilities.formatDate(now, 'Asia/Tokyo', 'yyyy-MM-dd HH:mm (E)');
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  
  const prompt = `
現在の日時: ${currentDate}
現在の年: ${currentYear}
現在の月: ${currentMonth}

以下の日本語テキストから予定情報を抽出し、JSONのみを返してください。
長文の場合でも、テキスト内に含まれる日時・場所・イベント名を正確に抽出してください。

抽出項目：
- title: 予定のタイトル（イベント名、講演会名、会議名など）
- date: 開始日 (YYYY-MM-DD形式)。繰り返し予定の場合は最初の該当日を設定。
- endDate: 終了日 (YYYY-MM-DD形式)。単日の場合はnull、複数日の場合は最終日を設定。
- startTime: 開始時間 (HH:MM形式)
- endTime: 終了時間 (HH:MM形式)
- isAllDay: 終日か (true/false)
- location: 場所・会議室名など（あれば）
- recurrence: 繰り返しパターン (なければnull)
- description: 詳細（元テキストの要約や重要な情報）

重要なルール - 日付認識:
1. 年が省略されている場合は${currentYear}年と仮定する
2. 月のみの場合で現在月より小さい場合は翌年と仮定
3. 日付表現の例：
   - "7月16日" → "2025-07-16"
   - "7月16日（水）" → "2025-07-16"（曜日は無視）
   - "12/25" → "2025-12-25"
   - "1月5日" → 現在が12月なら"2026-01-05"、それ以外なら"2025-01-05"
   - "明日" → 現在日時から計算
   - "来週火曜" → 現在日時から計算

重要なルール - 複数日イベント:
1. 期間を表す表現（「○日から○日まで」「○日〜○日」「3日間の」等）は、必ず1つのイベントとして扱う
2. 複数日イベントの場合、必ずendDateに最終日を設定する
3. 絶対にやってはいけないこと：複数日の予定を複数のイベントに分割すること

重要なルール - タイトル抽出:
1. 【】や「」で囲まれた部分はタイトルの最優先候補
2. 講演会、セミナー、会議、研修などのイベント名を適切に抽出
3. 不要な説明文は除外し、簡潔なタイトルにする

重要なルール - 場所抽出:
1. "場所："、"会場："、"場所：**"のような明示的な記載を優先
2. "○階 会議室○"、"オンライン"、"Zoom"、"Teams"などを認識
3. 住所や建物名も場所として認識

重要なルール - その他:
- 時間が明記されていなければ終日(isAllDay: true)とみなす
- 終了時間がなければ、講演会・セミナーは記載時間通り、会議は1時間、食事は1.5時間、その他は1時間とする
- 繰り返し：「毎週月曜日」→"weekly:月"、「毎月第1月曜日」→"monthly:第1月"、「毎日」→"daily"

処理例1: 長文からの抽出
入力: "【小児アトピー性皮膚炎治療に関するWeb講演会 視聴会のお知らせ】リジェネロン・ジャパン株式会社から情報提供があり、Web講演会の視聴会を開催します。アトピー性皮膚炎の治療・診療に役立てていただける内容ですので、よろしければ是非ご参加ください。「それいけ！小児アトピーのミライへ！」日時：**7月16日（水）19:00～20:20**場所：**４階 会議室１**"

出力例: {
  "title": "小児アトピー性皮膚炎治療に関するWeb講演会 視聴会",
  "date": "2025-07-16",
  "endDate": null,
  "startTime": "19:00",
  "endTime": "20:20",
  "isAllDay": false,
  "location": "４階 会議室１",
  "recurrence": null,
  "description": "それいけ！小児アトピーのミライへ！リジェネロン・ジャパン株式会社主催"
}

処理例2: 複数日イベント
入力: "4月17日から19日の学術集会に参加"
出力: {"title": "学術集会", "date": "2025-04-17", "endDate": "2025-04-19", "startTime": null, "endTime": null, "isAllDay": true, "location": null, "recurrence": null, "description": null}

処理例3: 繰り返し予定
入力: "毎週木曜日16時から放射線カンファレンス"
出力: {"title": "放射線カンファレンス", "date": "2025-07-10", "endDate": null, "startTime": "16:00", "endTime": "17:00", "isAllDay": false, "location": null, "recurrence": "weekly:木", "description": null}

入力テキスト: "${text}"

JSONを返してください（説明や\`\`\`は不要）:`;
  
  return callGemini(prompt);
}

/**
 * 削除・変更のために、テキストから検索キーワードと日付範囲を抽出します（改善版）。
 * @param {string} text - ユーザーの入力テキスト
 * @return {object} - {keywords: Array<string>, dateRange: string|null}
 */
function parseSearchKeywordsWithGemini(text) {
  const now = new Date();
  const currentDate = Utilities.formatDate(now, 'Asia/Tokyo', 'yyyy-MM-dd HH:mm (E)');
  
  const prompt = `
現在の日時: ${currentDate}
以下のテキストから、Googleカレンダーの予定を検索するための情報を抽出してください。

抽出項目：
- keywords: 予定のタイトルに含まれていそうな単語を1〜3個抽出（配列）
- dateRange: 日付の指定があれば抽出（なければnull）

重要な点：
- keywordsには「削除」「変更」「キャンセル」などの操作を表す単語は含めない
- dateRangeの値は以下のいずれかを返す：
  - "今日": 今日の予定のみ
  - "明日": 明日の予定のみ  
  - "YYYY-MM-DD": 具体的な日付（例：2025-01-15）
  - "今週": 今週の予定のみ
  - "来週": 来週の予定のみ
  - "今月": 今月の予定のみ
  - null: 日付指定なし（未来日のみ検索）

例：
- 入力：「明日の会議を削除して」→ {"keywords": ["会議"], "dateRange": "明日"}
- 入力：「ランチタイム講義を削除」→ {"keywords": ["ランチタイム", "講義"], "dateRange": null}
- 入力：「1月15日の打ち合わせを変更」→ {"keywords": ["打ち合わせ"], "dateRange": "2025-01-15"}
- 入力：「来週の定例会をキャンセル」→ {"keywords": ["定例会"], "dateRange": "来週"}

入力テキスト: "${text}"

JSON形式で回答してください：
{"keywords": ["キーワード1"], "dateRange": "明日"}
`;
  
  try {
    const parsed = callGemini(prompt);
    if (parsed && parsed.keywords && Array.isArray(parsed.keywords)) {
      // 空文字列やnullを除去
      const cleanedKeywords = parsed.keywords.filter(keyword => keyword && typeof keyword === 'string' && keyword.trim().length > 0);
      if (cleanedKeywords.length > 0) {
        console.log(`抽出されたキーワード: ${cleanedKeywords.join(', ')}, 日付範囲: ${parsed.dateRange || 'なし'}`);
        return {
          keywords: cleanedKeywords,
          dateRange: parsed.dateRange || null
        };
      }
    }
  } catch (e) {
    console.log(`AIによるキーワード抽出に失敗: ${e.message}`);
  }
  
  // フォールバック：基本的な処理でキーワードを抽出
  const cleanText = text.replace(/削除|キャンセル|取り消し|消して|変更|修正|移動|変えて|移して|教えて|確認|明日|今日|来週|今週|来月|今月|月曜|火曜|水曜|木曜|金曜|土曜|日曜/g, '').trim();
  const fallbackKeywords = cleanText.split(/\s+/).filter(word => word.length > 0);
  
  if (fallbackKeywords.length > 0) {
    console.log(`フォールバックキーワード: ${fallbackKeywords.join(', ')}`);
    return {
      keywords: fallbackKeywords.slice(0, 3),
      dateRange: null
    };
  }
  
  return {
    keywords: [''],
    dateRange: null
  };
}

/**
 * 予定「変更」のためにテキストを解析します（複数日・終日イベント対応強化版）。
 */
function parseModificationQueryWithGemini(text) {
    const now = new Date();
    const currentDate = Utilities.formatDate(now, 'Asia/Tokyo', 'yyyy-MM-dd HH:mm (E)');
    const currentYear = now.getFullYear();

    const prompt = `
現在の日時: ${currentDate}
現在の年: ${currentYear}

以下のテキストから、カレンダーの予定変更に関する情報を抽出してください。

抽出項目:
- searchKeywords: 変更対象の予定を検索するためのキーワードの配列
- dateRange: 検索対象の日付範囲（下記参照）
- modification: 変更後の情報（変更したい項目のみ）
  - title: 新しいタイトル
  - date: 新しい開始日 (YYYY-MM-DD形式)
  - endDate: 新しい終了日 (YYYY-MM-DD形式、単日の場合はnull、複数日の場合は最終日)
  - startTime: 新しい開始時間 (HH:MM形式)
  - endTime: 新しい終了時間 (HH:MM形式)
  - isAllDay: 終日イベントにするか (true/false)
  - location: 新しい場所

検索日付範囲の値:
- "今日": 今日の予定のみ
- "明日": 明日の予定のみ
- "YYYY-MM-DD": 具体的な日付
- "今週": 今週の予定のみ
- "来週": 来週の予定のみ
- "今月": 今月の予定のみ
- null: 日付指定なし（未来日のみ検索）

重要なルール:
1. searchKeywordsには「変更」「修正」「移動」「延長」「短縮」などの操作を表す単語は含めない
2. 複数日の期間表現（「○日から○日まで」「○日〜○日」）は、dateとendDateの両方を設定する
3. 終日イベントの指示（「終日」「終日イベント」「一日中」）があればisAllDay: trueを設定
4. 年が明記されていない場合は${currentYear}年と仮定
5. 変更されない項目はmodificationに含めない
6. 「〜まで延長」「〜に短縮」などの表現は適切にendDateまたはendTimeに反映
7. 時間指定から終日への変更、終日から時間指定への変更も考慮する

例1: 複数日終日イベントへの変更
- 入力：「第14回インテンシブコースの予定を8月2日から3日の終日イベントに変更」
- 出力：{"searchKeywords": ["第14回", "インテンシブコース"], "dateRange": null, "modification": {"date": "2025-08-02", "endDate": "2025-08-03", "isAllDay": true}}

例2: 単日終日イベントへの変更
- 入力：「明日の会議を終日イベントに変更」
- 出力：{"searchKeywords": ["会議"], "dateRange": "明日", "modification": {"isAllDay": true}}

例3: 時間指定の変更
- 入力：「明日の会議を15時から17時に変更」
- 出力：{"searchKeywords": ["会議"], "dateRange": "明日", "modification": {"startTime": "15:00", "endTime": "17:00"}}

例4: 期間の延長
- 入力：「学会参加を8月5日まで延長」
- 出力：{"searchKeywords": ["学会", "参加"], "dateRange": null, "modification": {"endDate": "2025-08-05"}}

例5: 日付の移動
- 入力：「定例会を来週月曜に移動」
- 出力：{"searchKeywords": ["定例会"], "dateRange": null, "modification": {"date": "2025-07-14"}}

例6: 場所の変更
- 入力：「会議をオンラインに変更」
- 出力：{"searchKeywords": ["会議"], "dateRange": null, "modification": {"location": "オンライン"}}

例7: タイトルの変更
- 入力：「ミーティングの名前を定例会議に変更」
- 出力：{"searchKeywords": ["ミーティング"], "dateRange": null, "modification": {"title": "定例会議"}}

例8: 終日から時間指定への変更
- 入力：「終日の研修を10時から17時に変更」
- 出力：{"searchKeywords": ["研修"], "dateRange": null, "modification": {"startTime": "10:00", "endTime": "17:00", "isAllDay": false}}

例9: 複数項目の同時変更
- 入力：「会議を明日の14時から16時、会議室Bに変更」
- 出力：{"searchKeywords": ["会議"], "dateRange": null, "modification": {"date": "2025-07-09", "startTime": "14:00", "endTime": "16:00", "location": "会議室B"}}

入力テキスト: "${text}"

JSON形式で回答してください（説明や\`\`\`は不要）:`;
    
    return callGemini(prompt);
}

// ===================================================================
// Google Calendar 関連 (イベント操作) - 複数日対応追加
// ===================================================================

/**
 * キーワードと日付範囲を元にカレンダーを検索します（改善版）。
 * @param {Array<string>} keywords - 検索キーワードの配列
 * @param {string|null} dateRange - 日付範囲の指定
 * @return {Array} - 発見されたイベントオブジェクトの配列
 */
function findEventsByKeywords(keywords, dateRange = null) {
  if (!keywords || keywords.length === 0) {
    console.log('検索キーワードが空のため、処理を中止します。');
    return [];
  }
  
  // 空文字列やnullを除去
  const cleanKeywords = keywords.filter(keyword => keyword && typeof keyword === 'string' && keyword.trim().length > 0);
  
  if (cleanKeywords.length === 0) {
    console.log('有効な検索キーワードがないため、処理を中止します。');
    return [];
  }
  
  // 日付範囲の決定
  const { startTime, endTime } = getSearchDateRange(dateRange);
  console.log(`検索範囲: ${Utilities.formatDate(startTime, 'Asia/Tokyo', 'yyyy-MM-dd')} 〜 ${Utilities.formatDate(endTime, 'Asia/Tokyo', 'yyyy-MM-dd')}`);
  
  const calendar = CalendarApp.getCalendarById(CONFIG.CALENDAR_ID);
  let allEvents = [];
  
  // 各キーワードで個別に検索し、結果をマージ
  for (const keyword of cleanKeywords) {
    try {
      console.log(`キーワード「${keyword}」で検索中...`);
      const events = calendar.getEvents(startTime, endTime, { search: keyword });
      allEvents = allEvents.concat(events);
    } catch (error) {
      console.log(`キーワード「${keyword}」の検索でエラー: ${error.message}`);
    }
  }
  
  // 重複を除去（イベントIDベース）
  const uniqueEvents = [];
  const seenIds = new Set();
  
  for (const event of allEvents) {
    const eventId = event.getId();
    if (!seenIds.has(eventId)) {
      seenIds.add(eventId);
      uniqueEvents.push(event);
    }
  }
  
  console.log(`${uniqueEvents.length}件のユニークな予定が見つかりました。`);

  // CalendarEventオブジェクトと基本情報の両方を返す
  return uniqueEvents.map(event => ({
    id: event.getId(),
    title: event.getTitle(),
    startTime: event.getStartTime(),
    endTime: event.getEndTime(),
    eventObject: event // 実際のCalendarEventオブジェクトを保持
  }));
}

/**
 * 日付範囲指定から検索用の開始・終了日時を取得します。
 * @param {string|null} dateRange - 日付範囲の指定
 * @return {object} - {startTime: Date, endTime: Date}
 */
function getSearchDateRange(dateRange) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  if (!dateRange) {
    // 日付指定なし：今日から未来のみ検索
    const endTime = new Date(today);
    endTime.setDate(today.getDate() + 60); // 今日から60日後まで
    endTime.setHours(23, 59, 59, 999);
    return { startTime: today, endTime: endTime };
  }
  
  let startTime, endTime;
  
  switch (dateRange) {
    case '今日':
      startTime = new Date(today);
      endTime = new Date(today);
      endTime.setHours(23, 59, 59, 999);
      break;
      
    case '明日':
      startTime = new Date(today);
      startTime.setDate(today.getDate() + 1);
      endTime = new Date(startTime);
      endTime.setHours(23, 59, 59, 999);
      break;
      
    case '今週':
      const dayOfWeek = today.getDay();
      startTime = new Date(today);
      startTime.setDate(today.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1)); // 週の始まりを月曜に
      endTime = new Date(startTime);
      endTime.setDate(startTime.getDate() + 6);
      endTime.setHours(23, 59, 59, 999);
      break;
      
    case '来週':
      const nextWeekDay = today.getDay();
      startTime = new Date(today);
      startTime.setDate(today.getDate() - nextWeekDay + (nextWeekDay === 0 ? -6 : 1) + 7);
      endTime = new Date(startTime);
      endTime.setDate(startTime.getDate() + 6);
      endTime.setHours(23, 59, 59, 999);
      break;
      
    case '今月':
      startTime = new Date(today);
      startTime.setDate(1);
      endTime = new Date(startTime);
      endTime.setMonth(startTime.getMonth() + 1, 0);
      endTime.setHours(23, 59, 59, 999);
      break;
      
    default:
      // 具体的な日付の場合（YYYY-MM-DD形式）
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateRange)) {
        startTime = new Date(dateRange);
        endTime = new Date(dateRange);
        endTime.setHours(23, 59, 59, 999);
      } else {
        // 不明な場合は今日から未来のみ
        startTime = new Date(today);
        endTime = new Date(today);
        endTime.setDate(today.getDate() + 60);
        endTime.setHours(23, 59, 59, 999);
      }
      break;
  }
  
  return { startTime, endTime };
}

/**
 * 予定をカレンダーに追加します（複数日対応）。
 */
function addEventToCalendar(eventData) {
  try {
    if (eventData.recurrence) {
      return createEventWithCalendarAPI(eventData);
    }
    return createEventWithGAS(eventData);
  } catch (error) {
    console.error('カレンダー追加エラー:', error.stack);
    throw new Error(`カレンダーへの追加に失敗しました: ${error.message}`);
  }
}

/**
 * Calendar API (Advanced Service) を使って予定を作成します（複数日対応）。
 */
function createEventWithCalendarAPI(eventData) {
  const { title, date, endDate, startTime, endTime, isAllDay, location, recurrence, description } = eventData;
  const event = { summary: title, description: description || '' };

  // 場所の設定
  if (location) {
    event.location = location;
  }

  if (isAllDay) {
    event.start = { date: date };
    
    if (endDate && endDate !== date) {
      // 複数日の終日イベント
      const finalDate = new Date(endDate);
      finalDate.setDate(finalDate.getDate() + 1); // Calendar APIは終了日の翌日を指定
      event.end = { date: finalDate.toISOString().split('T')[0] };
      console.log(`複数日終日イベント作成: ${date} 〜 ${endDate}`);
    } else {
      // 単日の終日イベント
      event.end = { date: new Date(new Date(date).getTime() + 24 * 60 * 60 * 1000).toISOString().split('T')[0] };
      console.log(`単日終日イベント作成: ${date}`);
    }
  } else {
    const startDateTime = new Date(`${date}T${startTime || '09:00'}:00`);
    const endDateTime = new Date(`${date}T${endTime || '10:00'}:00`);
    if (isNaN(startDateTime.getTime())) throw new Error('Invalid time value');
    event.start = { dateTime: startDateTime.toISOString(), timeZone: 'Asia/Tokyo' };
    event.end = { dateTime: endDateTime.toISOString(), timeZone: 'Asia/Tokyo' };
  }

  if (recurrence) {
    const rrule = convertToRRule(recurrence);
    if (rrule) event.recurrence = [rrule];
  }

  try {
    const calendarId = CONFIG.CALENDAR_ID;
    const createdEvent = Calendar.Events.insert(event, calendarId);
    console.log('✅ Calendar APIで予定作成完了:', createdEvent.summary);
    return {
      id: createdEvent.id,
      title: createdEvent.summary,
      startTime: isAllDay ? new Date(createdEvent.start.date) : new Date(createdEvent.start.dateTime),
      endTime: isAllDay ? new Date(createdEvent.end.date) : new Date(createdEvent.end.dateTime),
      isAllDay: !!isAllDay,
      location: createdEvent.location || null,
      recurrence: recurrence,
      htmlLink: createdEvent.htmlLink,
      endDate: endDate || null // 複数日情報を保持
    };
  } catch (apiError) {
    console.error('Calendar APIエラー:', apiError.stack);
    console.log('フォールバック: GAS標準メソッドで作成します');
    return createEventWithGAS(eventData);
  }
}

/**
 * GAS標準のCalendarAppを使って予定を作成します（複数日対応・デバッグ強化）。
 */
function createEventWithGAS(eventData) {
  const { title, date, endDate, startTime, endTime, isAllDay, location, description } = eventData;
  
  console.log(`カレンダー作成開始:`, JSON.stringify(eventData, null, 2));
  
  const calendar = CalendarApp.getCalendarById(CONFIG.CALENDAR_ID);
  const options = { description: description || '' };
  
  // 場所の設定
  if (location) {
    options.location = location;
  }

  let createdEvent;
  if (isAllDay) {
    const startDate = new Date(date);
    console.log(`終日イベント作成: 開始日=${date}, 終了日=${endDate || 'なし'}`);
    
    if (endDate && endDate !== date) {
      // 複数日の終日イベント
      const finalDate = new Date(endDate);
      finalDate.setDate(finalDate.getDate() + 1); // Google Calendarは終了日の翌日を指定
      
      console.log(`複数日終日イベント: ${startDate.toISOString().split('T')[0]} 〜 ${finalDate.toISOString().split('T')[0]}`);
      
      createdEvent = calendar.createAllDayEvent(title, startDate, finalDate, options);
      console.log(`✅ 複数日終日イベント作成完了: ${date} 〜 ${endDate}`);
    } else {
      // 単日の終日イベント
      console.log(`単日終日イベント: ${startDate.toISOString().split('T')[0]}`);
      createdEvent = calendar.createAllDayEvent(title, startDate, options);
      console.log(`✅ 単日終日イベント作成完了: ${date}`);
    }
  } else {
    // 時間指定イベント（複数日は未対応、単日のみ）
    const startDateTime = new Date(`${date}T${startTime || '09:00'}:00`);
    const endDateTime = new Date(`${date}T${endTime || '10:00'}:00`);
    if (isNaN(startDateTime.getTime())) throw new Error('Invalid time value');
    
    console.log(`時間指定イベント: ${startDateTime.toISOString()} 〜 ${endDateTime.toISOString()}`);
    createdEvent = calendar.createEvent(title, startDateTime, endDateTime, options);
    console.log(`✅ 時間指定イベント作成完了: ${date} ${startTime}-${endTime}`);
  }
  
  // 作成されたイベントの詳細をログ出力
  console.log(`作成されたイベント詳細:`);
  console.log(`- ID: ${createdEvent.getId()}`);
  console.log(`- タイトル: ${createdEvent.getTitle()}`);
  console.log(`- 開始: ${createdEvent.getStartTime()}`);
  console.log(`- 終了: ${createdEvent.getEndTime()}`);
  console.log(`- 終日: ${createdEvent.isAllDayEvent()}`);
  
  return {
      id: createdEvent.getId(),
      title: createdEvent.getTitle(),
      startTime: createdEvent.getStartTime(),
      endTime: createdEvent.getEndTime(),
      isAllDay: createdEvent.isAllDayEvent(),
      location: createdEvent.getLocation() || null,
      recurrence: null,
      htmlLink: `https://calendar.google.com/calendar`,
      endDate: endDate || null // 複数日情報を保持
  };
}

/**
 * イベントIDを指定して、カレンダーからイベントオブジェクトを取得します。
 */
function getEventById(eventId) {
    try {
        const calendar = CalendarApp.getCalendarById(CONFIG.CALENDAR_ID);
        return calendar.getEventById(eventId);
    } catch (e) {
        console.error(`イベント取得失敗 ID: ${eventId}`, e);
        return null;
    }
}

/**
 * 繰り返しパターンをGoogle Calendar API用のRRULE形式に変換します。
 */
function convertToRRule(recurrencePattern) {
  if (!recurrencePattern) return null;
  const pattern = recurrencePattern.toLowerCase();

  if (pattern === 'daily') return 'RRULE:FREQ=DAILY;COUNT=365';
  if (pattern.startsWith('weekly:')) {
    const dayMap = {'月':'MO','火':'TU','水':'WE','木':'TH','金':'FR','土':'SA','日':'SU'};
    const day = dayMap[pattern.split(':')[1]];
    if(day) return `RRULE:FREQ=WEEKLY;BYDAY=${day};COUNT=52`;
  }
  if (pattern.startsWith('monthly:第')) { // 毎月第○△曜日
    const match = pattern.match(/第(\d+)([月火水木金土日])/);
    if (match) {
      const week = match[1];
      const dayStr = match[2];
      const dayMap = {'月':'MO','火':'TU','水':'WE','木':'TH','金':'FR','土':'SA','日':'SU'};
      const day = dayMap[dayStr];
      if(day) return `RRULE:FREQ=MONTHLY;BYDAY=${week}${day};COUNT=12`;
    }
  }
  return null;
}

// ===================================================================
// Slack メッセージング関連
// ===================================================================

/**
 * Slackにメッセージを送信します。
 */
function sendSlackMessage(channel, text, userId, blocks) {
  const payload = { channel: channel, text: text || ' ' };
  if (blocks) payload.blocks = blocks.blocks;
  if (userId && text) payload.text = `<@${userId}> ${text}`;

  const options = {
    method: 'POST',
    contentType: 'application/json',
    headers: { 'Authorization': `Bearer ${CONFIG.SLACK_BOT_TOKEN}` },
    payload: JSON.stringify(payload)
  };

  try {
    UrlFetchApp.fetch('https://slack.com/api/chat.postMessage', options);
  } catch(e) {
    console.error("Slackへの送信に失敗しました: ", e);
  }
}

/**
 * 既存のSlackメッセージを更新します（ボタンを消すなどに使用）。
 */
function updateSlackMessage(channel, ts, text, blocks) {
    const payload = {
        channel: channel,
        ts: ts,
        text: text || ' '
    };
    
    if (blocks && blocks.blocks) {
        payload.blocks = blocks.blocks;
    } else if (text) {
        payload.blocks = [{
            type: 'section',
            text: { type: 'mrkdwn', text: text }
        }];
    }
    
    try {
        UrlFetchApp.fetch('https://slack.com/api/chat.update', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + CONFIG.SLACK_BOT_TOKEN },
            contentType: 'application/json',
            payload: JSON.stringify(payload)
        });
    } catch (error) {
        console.error('Slackメッセージ更新エラー:', error);
    }
}

/**
 * 予定追加の確認メッセージを送信します（複数日対応）。
 * @param {string} channel - SlackチャンネルID
 * @param {string} user - ユーザーID
 * @param {object} eventData - 追加予定のデータ
 */
function sendAddConfirmationMessage(channel, user, eventData) {
  const { title, date, endDate, startTime, endTime, isAllDay, location, recurrence, description } = eventData;
  
  // 日時の表示形式を整える（複数日対応）
  let timeText = '';
  if (isAllDay) {
    if (endDate && endDate !== date) {
      // 複数日の終日イベント
      const startDateFormatted = Utilities.formatDate(new Date(date), 'Asia/Tokyo', 'M月d日(E)');
      const endDateFormatted = Utilities.formatDate(new Date(endDate), 'Asia/Tokyo', 'M月d日(E)');
      const days = Math.ceil((new Date(endDate) - new Date(date)) / (1000 * 60 * 60 * 24)) + 1;
      timeText = `${startDateFormatted} 〜 ${endDateFormatted}（${days}日間・終日）`;
    } else {
      // 単日の終日イベント
      const eventDate = Utilities.formatDate(new Date(date), 'Asia/Tokyo', 'M月d日(E)');
      timeText = `${eventDate}（終日）`;
    }
  } else {
    const eventDate = Utilities.formatDate(new Date(date), 'Asia/Tokyo', 'M月d日(E)');
    const start = startTime || '09:00';
    const end = endTime || '10:00';
    timeText = `${eventDate} ${start} 〜 ${end}`;
  }
  
  // 場所の表示
  let locationText = '';
  if (location) {
    locationText = `\n*📍 場所:* ${location}`;
  }
  
  // 繰り返しの表示
  let recurrenceText = '';
  if (recurrence) {
    recurrenceText = `\n*🔄 繰り返し:* ${recurrence}`;
  }
  
  // 説明の表示
  let descriptionText = '';
  if (description) {
    descriptionText = `\n*📝 詳細:* ${description}`;
  }
  
  const confirmationText = `*📅 予定名:* ${title}\n*🕐 日時:* ${timeText}${locationText}${recurrenceText}${descriptionText}`;
  
  const value = { 
    action: 'add', 
    eventData: eventData 
  };
  
  const blocks = [{
    type: 'section', 
    text: { type: 'mrkdwn', text: `<@${user}> 以下の予定を追加しますか？\n\n${confirmationText}` }
  }, {
    type: 'actions', 
    elements: [{
      type: 'button', 
      text: { type: 'plain_text', text: 'はい、追加する' },
      style: 'primary',
      action_id: 'confirm_add', 
      value: JSON.stringify(value)
    }, {
      type: 'button', 
      text: { type: 'plain_text', text: 'いいえ' },
      action_id: 'cancel_action'
    }]
  }];
  
  sendSlackMessage(channel, '予定の確認をお願いします。', null, { blocks: blocks });
}

/**
 * 候補が複数ある場合に、ユーザーに選択を促すメッセージを送信します。
 */
function sendEventClarificationMessage(channel, user, events, action, details) {
    const blocks = [{
        type: 'section',
        text: { type: 'mrkdwn', text: `<@${user}> どの予定について操作しますか？` }
    }];

    events.slice(0, 5).forEach(event => {
        const time = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M/d HH:mm');
        const value = { 
            action: action, 
            eventId: event.id, 
            details: details || null,
            // 検索結果から取得した正確な日付情報を含める
            eventInfo: {
                title: event.title,
                startTime: event.startTime.getTime(), // timestampとして保存
                endTime: event.endTime.getTime()
            }
        };
        blocks.push({
            type: 'section',
            text: { type: 'mrkdwn', text: `*${event.title}*\n>${time}〜` },
            accessory: {
                type: 'button',
                text: { type: 'plain_text', text: 'これを選択' },
                action_id: `select_event_${action}`,
                value: JSON.stringify(value)
            }
        });
    });

    sendSlackMessage(channel, 'どの予定か選んでください。', null, { blocks: blocks });
}

/**
 * 操作の最終確認メッセージを送信します（変更内容プレビュー強化版）。
 * @param {object} event - 正式な CalendarEvent オブジェクト
 */
function sendConfirmationMessage(channel, user, event, action, details) {
    let text = '';
    const eventTime = Utilities.formatDate(event.getStartTime(), "Asia/Tokyo", "M月d日(E) HH:mm");
    const eventTitle = event.getTitle();

    if (action === 'delete') {
        // 削除の確認処理（変更なし）
        const isRecurring = isRecurringEvent(event);
        
        if (isRecurring) {
            sendRecurringEventDeleteDialog(channel, user, event, eventTime, eventTitle);
        } else {
            text = `*「${eventTitle} (${eventTime}〜)」* を本当に削除しますか？`;
            const value = { action: action, eventId: event.getId(), details: details || null };
            const blocks = [{
                type: 'section', text: { type: 'mrkdwn', text: `<@${user}> ${text}` }
            }, {
                type: 'actions', elements: [{
                    type: 'button', text: { type: 'plain_text', text: 'はい、削除する' },
                    style: 'danger',
                    action_id: 'confirm_delete', value: JSON.stringify(value)
                }, {
                    type: 'button', text: { type: 'plain_text', text: 'いいえ' },
                    action_id: 'cancel_action'
                }]
            }];
            sendSlackMessage(channel, '最終確認です。', null, { blocks: blocks });
        }
    } else if (action === 'modify') {
        const mod = details.modification;
        let changeDescription = [];
        
        // タイトルの変更
        if (mod.title) {
            changeDescription.push(`タイトルを *${mod.title}* に`);
        }
        
        // 日付の変更
        if (mod.date) {
            if (mod.endDate && mod.endDate !== mod.date) {
                // 複数日の場合
                const startDateFormatted = Utilities.formatDate(new Date(mod.date), 'Asia/Tokyo', 'M月d日');
                const endDateFormatted = Utilities.formatDate(new Date(mod.endDate), 'Asia/Tokyo', 'M月d日');
                const days = Math.ceil((new Date(mod.endDate) - new Date(mod.date)) / (1000 * 60 * 60 * 24)) + 1;
                changeDescription.push(`期間を *${startDateFormatted}〜${endDateFormatted}（${days}日間）* に`);
            } else {
                // 単日の場合
                changeDescription.push(`日付を *${mod.date}* に`);
            }
        } else if (mod.endDate) {
            // 終了日のみの変更（期間延長など）
            const endDateFormatted = Utilities.formatDate(new Date(mod.endDate), 'Asia/Tokyo', 'M月d日');
            changeDescription.push(`終了日を *${endDateFormatted}* まで`);
        }
        
        // 終日イベントへの変更
        if (mod.isAllDay === true) {
            changeDescription.push('*終日イベント* に');
        } else if (mod.isAllDay === false) {
            changeDescription.push('*時間指定イベント* に');
        }
        
        // 時間の変更
        if (mod.startTime) {
            changeDescription.push(`開始時間を *${mod.startTime}* に`);
        }
        if (mod.endTime) {
            changeDescription.push(`終了時間を *${mod.endTime}* に`);
        }
        
        // 場所の変更
        if (mod.location) {
            changeDescription.push(`場所を *${mod.location}* に`);
        }
        
        if (changeDescription.length > 0) {
          text = `*「${eventTitle} (${eventTime}〜)」* の${changeDescription.join('、')}変更しますか？`;
        } else {
          text = `予定「${eventTitle}」への変更内容を認識できませんでした。操作をキャンセルしますか？`;
        }

        const value = { action: action, eventId: event.getId(), details: details || null };
        const blocks = [{
            type: 'section', text: { type: 'mrkdwn', text: `<@${user}> ${text}` }
        }, {
            type: 'actions', elements: [{
                type: 'button', text: { type: 'plain_text', text: 'はい、実行する' },
                style: 'primary',
                action_id: `confirm_${action}`, value: JSON.stringify(value)
            }, {
                type: 'button', text: { type: 'plain_text', text: 'いいえ' },
                action_id: 'cancel_action'
            }]
        }];
        sendSlackMessage(channel, '最終確認です。', null, { blocks: blocks });
    }
}

/**
 * 繰り返しイベントの削除選択ダイアログを送信します。
 */
function sendRecurringEventDeleteDialog(channel, user, event, eventTime, eventTitle) {
    const text = `*「${eventTitle} (${eventTime}〜)」* は繰り返し予定です。どのように削除しますか？`;
    const eventId = event.getId();
    
    const blocks = [{
        type: 'section', 
        text: { type: 'mrkdwn', text: `<@${user}> ${text}` }
    }, {
        type: 'actions', 
        elements: [{
            type: 'button', 
            text: { type: 'plain_text', text: 'この日のみ削除' },
            style: 'primary',
            action_id: 'delete_single_occurrence', 
            value: JSON.stringify({ eventId: eventId, deleteType: 'single' })
        }, {
            type: 'button', 
            text: { type: 'plain_text', text: 'この日以降すべて削除' },
            style: 'danger',
            action_id: 'delete_future_occurrences', 
            value: JSON.stringify({ eventId: eventId, deleteType: 'future' })
        }, {
            type: 'button', 
            text: { type: 'plain_text', text: 'シリーズ全体削除' },
            style: 'danger',
            action_id: 'delete_entire_series', 
            value: JSON.stringify({ eventId: eventId, deleteType: 'series' })
        }]
    }, {
        type: 'actions',
        elements: [{
            type: 'button', 
            text: { type: 'plain_text', text: 'キャンセル' },
            action_id: 'cancel_action'
        }]
    }];
    
    sendSlackMessage(channel, '削除方法を選択してください。', null, { blocks: blocks });
}

/**
 * イベントが繰り返しイベントかどうかを判定します。
 * @param {CalendarEvent} event - カレンダーイベント
 * @return {boolean} - 繰り返しイベントの場合true
 */
function isRecurringEvent(event) {
    try {
        // イベントのIDに繰り返しの情報が含まれているかチェック
        const eventId = event.getId();
        
        // 繰り返しイベントの場合、IDに特定のパターンが含まれる
        if (eventId.includes('_') && eventId.split('_').length > 1) {
            return true;
        }
        
        // 別の方法：イベントのrecurrenceプロパティをチェック
        // ただし、GASでは直接アクセスできないので、Calendar API経由で確認
        try {
            const calendar = CalendarApp.getCalendarById(CONFIG.CALENDAR_ID);
            const events = calendar.getEventSeriesById(eventId);
            return events !== null;
        } catch (e) {
            // getEventSeriesById でエラーが発生した場合、単発イベント
            return false;
        }
    } catch (error) {
        console.log('繰り返しイベント判定エラー:', error);
        return false;
    }
}

/**
 * 成功メッセージのBlock Kitを作成します（カレンダーボタン改善版）
 */
function createSuccessMessage(event, userId) {
  let timeText = '';
  if (event.isAllDay) {
    if (event.endDate && event.endDate !== Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'yyyy-MM-dd')) {
      // 複数日の終日イベント
      const startDateFormatted = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      const endDateFormatted = Utilities.formatDate(new Date(event.endDate), 'Asia/Tokyo', 'M月d日(E)');
      const days = Math.ceil((new Date(event.endDate) - event.startTime) / (1000 * 60 * 60 * 24)) + 1;
      timeText = `*🗓️ 期間:* ${startDateFormatted} 〜 ${endDateFormatted}（${days}日間・終日）`;
    } else {
      // 単日の終日イベント
      const eventDate = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E)');
      timeText = `*🗓️ 日付:* ${eventDate}（終日）`;
    }
  } else {
    const startTime = Utilities.formatDate(event.startTime, 'Asia/Tokyo', 'M月d日(E) HH:mm');
    const endTime = Utilities.formatDate(event.endTime, 'Asia/Tokyo', 'HH:mm');
    timeText = `*🕐 日時:* ${startTime} 〜 ${endTime}`;
  }

  let locationText = '';
  if (event.location) {
    locationText = `\n*📍 場所:* ${event.location}`;
  }

  const blocks = [{
    type: 'section',
    text: { type: 'mrkdwn', text: `<@${userId}> ✅ 予定を追加しました！\n\n*📅 予定名:* ${event.title}\n${timeText}${locationText}` }
  }, {
    type: 'actions', 
    elements: [{
      type: 'button', 
      text: { type: 'plain_text', text: 'カレンダーで確認' },
      action_id: 'open_calendar',
      style: 'primary',
      value: JSON.stringify({ 
        action: 'open_calendar', 
        url: event.htmlLink || 'https://calendar.google.com/calendar',
        eventTitle: event.title 
      })
    }]
  }];
  return { blocks: blocks };
}

/**
 * 予定リストの応答メッセージを作成します（改良版）。
 * @param {Array} events - CalendarEventオブジェクトの配列
 * @param {object} queryDetails - AIが解析した検索条件
 * @param {string} userId - ユーザーID
 * @param {Date} startTime - 検索開始日時
 * @param {Date} endTime - 検索終了日時
 * @return {object} - Slackメッセージ用のBlock Kitオブジェクト
 */
function formatEventListMessage(events, queryDetails, userId, startTime, endTime) {
  const keywordText = (queryDetails.keywords && Array.isArray(queryDetails.keywords) && queryDetails.keywords.length > 0) ? `「*${queryDetails.keywords.join(' ')}*」の` : '';
  
  // 日付範囲の表示を改善
  let rangeText;
  const isSameDay = startTime.toDateString() === endTime.toDateString();
  const isFullMonth = startTime.getDate() === 1 && endTime.getDate() === new Date(endTime.getFullYear(), endTime.getMonth() + 1, 0).getDate();
  const isFutureRange = Math.abs(endTime - startTime) > 30 * 24 * 60 * 60 * 1000; // 30日以上の範囲
  
  if (isSameDay) {
    // 同じ日の場合
    rangeText = Utilities.formatDate(startTime, 'Asia/Tokyo', 'M月d日(E)');
  } else if (isFullMonth) {
    // 月全体の場合
    rangeText = Utilities.formatDate(startTime, 'Asia/Tokyo', 'yyyy年M月');
  } else if (isFutureRange) {
    // 長期間（未来検索）の場合
    rangeText = '今後';
  } else {
    // 期間の場合
    const startStr = Utilities.formatDate(startTime, 'Asia/Tokyo', 'M/d');
    const endStr = Utilities.formatDate(endTime, 'Asia/Tokyo', 'M/d');
    rangeText = `${startStr}〜${endStr}`;
  }
  
  const headerText = `<@${userId}> ${rangeText}の${keywordText}予定はこちらです。`;

  const blocks = [{
      type: 'section',
      text: { type: 'mrkdwn', text: headerText }
  }];

  if (events.length === 0) {
      blocks.push({
          type: 'section',
          text: { type: 'mrkdwn', text: '該当する予定は見つかりませんでした。' }
      });
  } else {
      blocks.push({ type: 'divider' });
      events.slice(0, 15).forEach(event => { // 最大15件まで表示
          const start = event.getStartTime();
          const end = event.getEndTime();
          let timeInfo;
          if (event.isAllDayEvent()) {
              timeInfo = `終日`;
          } else {
              timeInfo = `${Utilities.formatDate(start, 'Asia/Tokyo', 'HH:mm')} - ${Utilities.formatDate(end, 'Asia/Tokyo', 'HH:mm')}`;
          }
          const dateStr = Utilities.formatDate(start, 'Asia/Tokyo', 'M月d日 (E)');
          
          let locationInfo = '';
          if (event.getLocation()) {
              locationInfo = ` 📍${event.getLocation()}`;
          }
          
          blocks.push({
              type: 'section',
              text: {
                  type: 'mrkdwn',
                  text: `*${event.getTitle()}*\n>${dateStr} \`[${timeInfo}]\`${locationInfo}`
              }
          });
      });
  }
  return { blocks: blocks };
}

/**
 * ヘルプメッセージを送信します。
 */
function sendHelpMessage(channel, userId) {
  const helpBlocks = {
    blocks: [
      { type: 'section', text: { type: 'mrkdwn', text: `<@${userId}> 📅 *カレンダーボットの使い方*` } },
      { type: 'divider' },
      { type: 'section', text: { type: 'mrkdwn', text: "*▶️ 予定の確認*\n「今日の予定を教えて」\n「来週の会議の予定は？」" }},
      { type: 'section', text: { type: 'mrkdwn', text: "*▶️ 予定の追加*\n「明日の14時から会議室Aで会議」\n「毎週月曜10時にオンラインで定例会」\n「4月17日から19日の学術集会」" }},
      { type: 'section', text: { type: 'mrkdwn', text: "*▶️ 予定の変更*\n「明日の会議を15時から17時に変更」\n「月曜の定例会の終了時間を16時に延長」" }},
      { type: 'section', text: { type: 'mrkdwn', text: "*▶️ 予定の削除*\n「明日の会議をキャンセル」\n「来週の予定を削除して」" }},
      { type: 'section', text: { type: 'mrkdwn', text: "*🔗 URLから予定追加*\nWebページのURLを送信すると予定情報を自動検出" }},
      { type: 'section', text: { type: 'mrkdwn', text: "*📄 PDFから予定追加*\nPDFファイルを添付すると予定情報を自動検出" }},
      { type: 'section', text: { type: 'mrkdwn', text: "*📝 Wordから予定追加*\nWordファイル(.docx)を添付すると予定情報を自動検出" }},
      { type: 'section', text: { type: 'mrkdwn', text: "*📊 PowerPointから予定追加*\nPowerPointファイル(.pptx)を添付すると予定情報を自動検出" }},
      { type: 'context', elements: [{ type: 'mrkdwn', text: '💡 複数日イベントや終日イベントにも対応しています' }] }
    ]
  };
  sendSlackMessage(channel, null, null, helpBlocks);
}

// ===================================================================
// Slack ボタン操作の処理（PDF機能対応追加）
// ===================================================================
/**
 * Slackのボタンクリックなどの対話操作を処理します。
 * @param {object} payload - block_actionsペイロード
 */
function processBlockActions(payload) {
    const { user, channel, actions, message } = payload;
    const action = actions[0];
    const action_id = action.action_id;
    const value = JSON.parse(action.value || '{}');

    // カレンダー確認ボタンの処理
    if (action_id === 'open_calendar') {
        const eventTitle = value.eventTitle || '予定';
        const finalMessage = `✅ ${eventTitle}の追加が完了しました！\n\n📅 カレンダーで予定を確認してください: https://calendar.google.com/calendar`;
        
        updateSlackMessage(channel.id, message.ts, finalMessage);
        return;
    }

    updateSlackMessage(channel.id, message.ts, `> _${message.text}_\n\n処理中です...`);

    try {
        if (action_id.startsWith('select_event_')) {
            // 複数選択の場合、検索結果の情報を使って確認ダイアログを表示
            if (value.eventInfo) {
                // 検索結果から取得した日付情報を使って仮のイベントオブジェクトを作成
                const mockEvent = {
                    getId: () => value.eventId,
                    getTitle: () => value.eventInfo.title,
                    getStartTime: () => new Date(value.eventInfo.startTime),
                    getEndTime: () => new Date(value.eventInfo.endTime)
                };
                sendConfirmationMessage(channel.id, user.id, mockEvent, value.action, value.details);
            } else {
                // フォールバック：getEventByIdを使用
                const event = getEventById(value.eventId);
                if (event) {
                    sendConfirmationMessage(channel.id, user.id, event, value.action, value.details);
                } else {
                    updateSlackMessage(channel.id, message.ts, 'エラー: 対象の予定が見つかりませんでした。');
                }
            }
        } else if (action_id.startsWith('confirm_add_from_combined')) {
            // *** 統合処理由来の予定追加 ***
            try {
                const createdEvent = addEventToCalendar(value.eventData);
                const sourceDescription = value.eventData.sourceInfo || '統合情報';
                const fileName = value.eventData.fileName || null;
                const successMessage = createCombinedScheduleSuccessMessage(createdEvent, user.id, sourceDescription, fileName);
                updateSlackMessage(channel.id, message.ts, null, successMessage);
            } catch (error) {
                console.error('統合予定追加エラー:', error);
                updateSlackMessage(channel.id, message.ts, `❌ 予定の追加に失敗しました: ${error.message}`);
            }
        } else if (action_id.startsWith('confirm_add_from_pdf')) {
            // PDF由来の予定追加処理
            try {
                const createdEvent = addEventToCalendar(value.eventData);
                const successMessage = createPDFScheduleSuccessMessage(createdEvent, user.id, value.eventData.sourceUrl || 'PDF');
                updateSlackMessage(channel.id, message.ts, null, successMessage);
            } catch (error) {
                console.error('PDF予定追加エラー:', error);
                updateSlackMessage(channel.id, message.ts, `❌ 予定の追加に失敗しました: ${error.message}`);
            }
        } else if (action_id === 'confirm_add_all_from_pdf') {
            // PDF由来の複数予定一括追加処理
            try {
                const eventDataArray = value.eventDataArray;
                const createdEvents = [];
                const failedEvents = [];
                
                for (const eventData of eventDataArray) {
                    try {
                        const createdEvent = addEventToCalendar(eventData);
                        createdEvents.push(createdEvent);
                    } catch (error) {
                        console.error(`予定追加失敗 - ${eventData.title}:`, error);
                        failedEvents.push(eventData.title);
                    }
                }
                
                const successMessage = createMultiplePDFScheduleSuccessMessage(
                    createdEvents, 
                    failedEvents, 
                    user.id, 
                    eventDataArray[0]?.sourceUrl || 'PDF'
                );
                updateSlackMessage(channel.id, message.ts, null, successMessage);
                
            } catch (error) {
                console.error('複数PDF予定追加エラー:', error);
                updateSlackMessage(channel.id, message.ts, `❌ 予定の一括追加に失敗しました: ${error.message}`);
            }
        } else if (action_id.startsWith('confirm_add_from_word')) {
            // Word由来の予定追加処理
            try {
                const createdEvent = addEventToCalendar(value.eventData);
                const successMessage = createWordScheduleSuccessMessage(createdEvent, user.id, value.eventData.sourceUrl || 'Wordファイル');
                updateSlackMessage(channel.id, message.ts, null, successMessage);
            } catch (error) {
                console.error('Word予定追加エラー:', error);
                updateSlackMessage(channel.id, message.ts, `❌ 予定の追加に失敗しました: ${error.message}`);
            }
        } else if (action_id.startsWith('confirm_add_from_powerpoint')) {
            // PowerPoint由来の予定追加処理
            try {
                const createdEvent = addEventToCalendar(value.eventData);
                const successMessage = createPowerPointScheduleSuccessMessage(createdEvent, user.id, value.eventData.sourceUrl || 'PowerPointファイル');
                updateSlackMessage(channel.id, message.ts, null, successMessage);
            } catch (error) {
                console.error('PowerPoint予定追加エラー:', error);
                updateSlackMessage(channel.id, message.ts, `❌ 予定の追加に失敗しました: ${error.message}`);
            }
        } else if (action_id.startsWith('confirm_add_from_url')) {
            // URL由来の予定追加処理
            try {
                const createdEvent = addEventToCalendar(value.eventData);
                const successMessage = createUrlScheduleSuccessMessage(createdEvent, user.id, value.eventData.sourceUrl);
                updateSlackMessage(channel.id, message.ts, null, successMessage);
            } catch (error) {
                console.error('URL予定追加エラー:', error);
                updateSlackMessage(channel.id, message.ts, `❌ 予定の追加に失敗しました: ${error.message}`);
            }
        } else if (action_id === 'confirm_add_all_from_url') {
            // URL由来の複数予定一括追加処理
            try {
                const eventDataArray = value.eventDataArray;
                const createdEvents = [];
                const failedEvents = [];
                
                for (const eventData of eventDataArray) {
                    try {
                        const createdEvent = addEventToCalendar(eventData);
                        createdEvents.push(createdEvent);
                    } catch (error) {
                        console.error(`予定追加失敗 - ${eventData.title}:`, error);
                        failedEvents.push(eventData.title);
                    }
                }
                
                const successMessage = createMultipleUrlScheduleSuccessMessage(
                    createdEvents, 
                    failedEvents, 
                    user.id, 
                    eventDataArray[0]?.sourceUrl
                );
                updateSlackMessage(channel.id, message.ts, null, successMessage);
                
            } catch (error) {
                console.error('複数URL予定追加エラー:', error);
                updateSlackMessage(channel.id, message.ts, `❌ 予定の一括追加に失敗しました: ${error.message}`);
            }
        } else if (action_id.startsWith('confirm_')) {
            if (value.action === 'add') {
                // 予定追加の確認処理
                try {
                    const createdEvent = addEventToCalendar(value.eventData);
                    const successMessage = createSuccessMessage(createdEvent, user.id);
                    updateSlackMessage(channel.id, message.ts, null, successMessage);
                } catch (error) {
                    console.error('予定追加エラー:', error);
                    updateSlackMessage(channel.id, message.ts, `❌ 予定の追加に失敗しました: ${error.message}`);
                }
            } else {
                // 既存の確認処理（削除・変更）
                const event = getEventById(value.eventId);
                if (!event) {
                    updateSlackMessage(channel.id, message.ts, 'エラー: 対象の予定が見つからないか、すでに削除されています。');
                    return;
                }

                if (value.action === 'delete') {
                    const title = event.getTitle();
                    event.deleteEvent();
                    updateSlackMessage(channel.id, message.ts, `✅ 予定「${title}」を削除しました。`);
                } else if (value.action === 'modify') {
                    handleEventModification(event, value.details.modification, channel.id, message.ts);
                }
            }
        } else if (action_id.startsWith('delete_')) {
            // 繰り返しイベント削除の処理
            handleRecurringEventDeletion(value, channel.id, message.ts);
        } else if (action_id === 'cancel_action') {
            updateSlackMessage(channel.id, message.ts, '操作をキャンセルしました。');
        }
    } catch (e) {
        console.error("Block Action Error:", e.stack);
        updateSlackMessage(channel.id, message.ts, `エラーが発生しました: ${e.message}`);
    }
}

/**
 * 繰り返しイベントの削除処理を実行します。
 * @param {object} value - ボタンから送信された値
 * @param {string} channelId - SlackチャンネルID
 * @param {string} messageTs - メッセージのタイムスタンプ
 */
function handleRecurringEventDeletion(value, channelId, messageTs) {
    const event = getEventById(value.eventId);
    if (!event) {
        updateSlackMessage(channelId, messageTs, 'エラー: 対象の予定が見つからないか、すでに削除されています。');
        return;
    }

    const title = event.getTitle();
    const eventDate = Utilities.formatDate(event.getStartTime(), "Asia/Tokyo", "M月d日(E)");
    
    try {
        switch (value.deleteType) {
            case 'single':
                // この日のみ削除
                event.deleteEvent();
                updateSlackMessage(channelId, messageTs, `✅ 予定「${title}」の${eventDate}のみを削除しました。`);
                break;
                
            case 'future':
                // この日以降すべて削除
                deleteEventAndFutureOccurrences(event);
                updateSlackMessage(channelId, messageTs, `✅ 予定「${title}」の${eventDate}以降をすべて削除しました。`);
                break;
                
            case 'series':
                // シリーズ全体削除
                deleteEntireEventSeries(event);
                updateSlackMessage(channelId, messageTs, `✅ 予定「${title}」のシリーズ全体を削除しました。`);
                break;
                
            default:
                updateSlackMessage(channelId, messageTs, 'エラー: 削除タイプが不明です。');
        }
    } catch (error) {
        console.error('繰り返しイベント削除エラー:', error);
        updateSlackMessage(channelId, messageTs, `エラーが発生しました: ${error.message}`);
    }
}

/**
 * 指定日以降の繰り返しイベントを削除します。
 * @param {CalendarEvent} event - 削除対象のイベント
 */
function deleteEventAndFutureOccurrences(event) {
    try {
        // Calendar APIを使用して今後の発生を削除
        const eventId = event.getId();
        const calendar = CalendarApp.getCalendarById(CONFIG.CALENDAR_ID);
        
        // この日以降のすべての発生を取得
        const startDate = new Date(event.getStartTime());
        const endDate = new Date();
        endDate.setFullYear(endDate.getFullYear() + 2); // 2年後まで
        
        const futureEvents = calendar.getEvents(startDate, endDate);
        const baseEventTitle = event.getTitle();
        
        // 同じタイトルの繰り返しイベントを削除
        let deletedCount = 0;
        futureEvents.forEach(futureEvent => {
            if (futureEvent.getTitle() === baseEventTitle && 
                futureEvent.getStartTime() >= startDate) {
                futureEvent.deleteEvent();
                deletedCount++;
            }
        });
        
        console.log(`${deletedCount}件の今後の発生を削除しました。`);
    } catch (error) {
        console.error('今後の発生削除エラー:', error);
        // フォールバック：単一イベントのみ削除
        event.deleteEvent();
    }
}

/**
 * 繰り返しイベントのシリーズ全体を削除します。
 * @param {CalendarEvent} event - 削除対象のイベント
 */
function deleteEntireEventSeries(event) {
    try {
        // イベントシリーズ全体を削除
        const eventId = event.getId();
        const calendar = CalendarApp.getCalendarById(CONFIG.CALENDAR_ID);
        
        // シリーズ全体を取得して削除
        try {
            const eventSeries = calendar.getEventSeriesById(eventId);
            if (eventSeries) {
                eventSeries.deleteEventSeries();
                return;
            }
        } catch (e) {
            console.log('getEventSeriesById失敗、代替手段を使用:', e.message);
        }
        
        // 代替手段：同じタイトルの全イベントを削除
        const startDate = new Date();
        startDate.setFullYear(startDate.getFullYear() - 1); // 1年前から
        const endDate = new Date();
        endDate.setFullYear(endDate.getFullYear() + 2); // 2年後まで
        
        const allEvents = calendar.getEvents(startDate, endDate);
        const baseEventTitle = event.getTitle();
        
        let deletedCount = 0;
        allEvents.forEach(calEvent => {
            if (calEvent.getTitle() === baseEventTitle) {
                calEvent.deleteEvent();
                deletedCount++;
            }
        });
        
        console.log(`${deletedCount}件のイベントを削除しました。`);
    } catch (error) {
        console.error('シリーズ全体削除エラー:', error);
        // フォールバック：単一イベントのみ削除
        event.deleteEvent();
    }
}

/**
 * イベントの変更処理を実行します（複数日・終日イベント対応強化版）。
 * @param {CalendarEvent} event - 変更対象のイベント
 * @param {object} modification - 変更内容
 * @param {string} channelId - SlackチャンネルID
 * @param {string} messageTs - メッセージのタイムスタンプ
 */
function handleEventModification(event, modification, channelId, messageTs) {
    const title = event.getTitle();
    const originalStartTime = event.getStartTime();
    const originalEndTime = event.getEndTime();
    const originalIsAllDay = event.isAllDayEvent();
    const originalLocation = event.getLocation() || '';
    const originalDescription = event.getDescription() || '';
    
    let changeDescription = [];
    let needsRecreation = false; // 複雑な変更の場合は再作成が必要

    try {
        // タイトルの変更
        if (modification.title) {
            event.setTitle(modification.title);
            changeDescription.push(`タイトルを *${modification.title}* に`);
        }

        // 複数日イベントへの変更や終日⇔時間指定の切り替えの場合は再作成が必要
        if (modification.endDate || 
            (modification.isAllDay !== undefined && modification.isAllDay !== originalIsAllDay) ||
            (modification.date && modification.isAllDay)) {
            needsRecreation = true;
        }

        if (needsRecreation) {
            // 複雑な変更の場合：既存イベントを削除して新しいイベントを作成
            const newEventData = {
                title: modification.title || title,
                date: modification.date || Utilities.formatDate(originalStartTime, 'Asia/Tokyo', 'yyyy-MM-dd'),
                endDate: modification.endDate || null,
                startTime: modification.startTime || (originalIsAllDay ? null : Utilities.formatDate(originalStartTime, 'Asia/Tokyo', 'HH:mm')),
                endTime: modification.endTime || (originalIsAllDay ? null : Utilities.formatDate(originalEndTime, 'Asia/Tokyo', 'HH:mm')),
                isAllDay: modification.isAllDay !== undefined ? modification.isAllDay : originalIsAllDay,
                location: modification.location || originalLocation,
                description: originalDescription
            };

            // 新しいイベントを作成
            const newEvent = addEventToCalendar(newEventData);
            
            // 既存イベントを削除
            event.deleteEvent();

            // 変更内容を記録
            if (modification.date) {
                changeDescription.push(`日付を *${modification.date}* に`);
            }
            if (modification.endDate) {
                const startDateFormatted = Utilities.formatDate(new Date(newEventData.date), 'Asia/Tokyo', 'M月d日');
                const endDateFormatted = Utilities.formatDate(new Date(modification.endDate), 'Asia/Tokyo', 'M月d日');
                changeDescription.push(`期間を *${startDateFormatted}〜${endDateFormatted}* に`);
            }
            if (modification.isAllDay !== undefined) {
                changeDescription.push(modification.isAllDay ? '*終日イベント* に' : '*時間指定イベント* に');
            }
            if (modification.startTime) {
                changeDescription.push(`開始時間を *${modification.startTime}* に`);
            }
            if (modification.endTime) {
                changeDescription.push(`終了時間を *${modification.endTime}* に`);
            }
            if (modification.location) {
                changeDescription.push(`場所を *${modification.location}* に`);
            }

        } else {
            // 単純な変更の場合：既存イベントを直接更新
            let newStartTime = new Date(originalStartTime);
            let newEndTime = new Date(originalEndTime);

            // 日付の変更（単日のみ）
            if (modification.date && !modification.endDate) {
                const [year, month, day] = modification.date.split('-');
                const timeDiff = newEndTime.getTime() - newStartTime.getTime(); // 持続時間を保持
                
                newStartTime.setFullYear(year, parseInt(month, 10) - 1, day);
                newEndTime = new Date(newStartTime.getTime() + timeDiff);
                
                changeDescription.push(`日付を *${modification.date}* に`);
            }

            // 開始時間の変更
            if (modification.startTime) {
                const [hours, minutes] = modification.startTime.split(':');
                const timeDiff = newEndTime.getTime() - newStartTime.getTime(); // 持続時間を保持
                
                newStartTime.setHours(hours, minutes, 0, 0);
                
                // 終了時間が指定されていない場合は、持続時間を保持
                if (!modification.endTime) {
                    newEndTime = new Date(newStartTime.getTime() + timeDiff);
                }
                
                changeDescription.push(`開始時間を *${modification.startTime}* に`);
            }

            // 終了時間の変更
            if (modification.endTime) {
                const [hours, minutes] = modification.endTime.split(':');
                newEndTime = new Date(newStartTime);
                newEndTime.setHours(hours, minutes, 0, 0);
                
                // 終了時間が開始時間より前の場合は、翌日と判定
                if (newEndTime <= newStartTime) {
                    newEndTime.setDate(newEndTime.getDate() + 1);
                }
                
                changeDescription.push(`終了時間を *${modification.endTime}* に`);
            }

            // 時間を設定
            if (modification.date || modification.startTime || modification.endTime) {
                event.setTime(newStartTime, newEndTime);
            }

            // 場所の変更
            if (modification.location) {
                event.setLocation(modification.location);
                changeDescription.push(`場所を *${modification.location}* に`);
            }
        }

        if (changeDescription.length > 0) {
            const successMessage = `✅ 予定「${title}」の${changeDescription.join('、')}変更しました。`;
            updateSlackMessage(channelId, messageTs, successMessage);
        } else {
            updateSlackMessage(channelId, messageTs, '⚠️ 変更内容を認識できませんでした。操作をキャンセルします。');
        }

    } catch (error) {
        console.error('イベント変更エラー:', error);
        updateSlackMessage(channelId, messageTs, `❌ 予定の変更中にエラーが発生しました: ${error.message}`);
    }
}

// ===================================================================
// ヘルパー関数
// ===================================================================

/**
 * AIが判定した期間キーワードから、具体的な開始・終了日時を取得します（具体的日付対応版）。
 * @param {string} timeRange - "今日", "2025-01-15", "2025-03" などの期間キーワード
 * @return {object} - {startTime: Date, endTime: Date}
 */
function getDateRange(timeRange) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  let startTime = new Date(today);
  let endTime;

  // 具体的な日付指定の場合（YYYY-MM-DD形式）
  if (/^\d{4}-\d{2}-\d{2}$/.test(timeRange)) {
    startTime = new Date(timeRange);
    endTime = new Date(timeRange);
    endTime.setHours(23, 59, 59, 999);
    return { startTime, endTime };
  }
  
  // 月指定の場合（YYYY-MM形式）
  if (/^\d{4}-\d{2}$/.test(timeRange)) {
    const [year, month] = timeRange.split('-');
    startTime = new Date(parseInt(year), parseInt(month) - 1, 1);
    endTime = new Date(parseInt(year), parseInt(month), 0); // 月の最終日
    endTime.setHours(23, 59, 59, 999);
    return { startTime, endTime };
  }

  // 既存の相対的な指定
  switch (timeRange) {
    case '今日':
      endTime = new Date(today);
      endTime.setHours(23, 59, 59, 999);
      break;
    case '明日':
      startTime.setDate(today.getDate() + 1);
      endTime = new Date(startTime);
      endTime.setHours(23, 59, 59, 999);
      break;
    case '今週':
      const dayOfWeek = today.getDay(); // 日=0, 月=1, ...
      startTime.setDate(today.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1)); // 週の始まりを月曜に設定
      endTime = new Date(startTime);
      endTime.setDate(startTime.getDate() + 6);
      endTime.setHours(23, 59, 59, 999);
      break;
    case '来週':
      const nextWeekDay = today.getDay();
      startTime.setDate(today.getDate() - nextWeekDay + (nextWeekDay === 0 ? -6 : 1) + 7);
      endTime = new Date(startTime);
      endTime.setDate(startTime.getDate() + 6);
      endTime.setHours(23, 59, 59, 999);
      break;
    case '今月':
      startTime.setDate(1);
      endTime = new Date(startTime);
      endTime.setMonth(startTime.getMonth() + 1, 0);
      endTime.setHours(23, 59, 59, 999);
      break;
    case '来月':
      startTime.setMonth(today.getMonth() + 1, 1);
      endTime = new Date(startTime);
      endTime.setMonth(startTime.getMonth() + 1, 0);
      endTime.setHours(23, 59, 59, 999);
      break;
    case '未来':
      // 今日から60日後まで
      startTime = new Date(today);
      endTime = new Date(today);
      endTime.setDate(today.getDate() + 60);
      endTime.setHours(23, 59, 59, 999);
      break;
    default: // デフォルトは今日
      endTime = new Date(today);
      endTime.setHours(23, 59, 59, 999);
      break;
  }
  return { startTime, endTime };
}

/**
 * 繰り返しルールから最初の該当日を計算します。
 * @param {string} recurrencePattern - "monthly:第2火" のような繰り返しパターン
 * @return {Date|null} - 計算された最初の該当日
 */
function getFirstOccurrenceDate(recurrencePattern, referenceDate = new Date()) {
  const pattern = recurrencePattern.toLowerCase();
  const today = new Date(referenceDate);
  today.setHours(0, 0, 0, 0);

  // 週次パターンの処理を追加
  if (pattern.startsWith('weekly:')) {
    const dayStr = pattern.split(':')[1];
    const dayMap = {'日':0, '月':1, '火':2, '水':3, '木':4, '金':5, '土':6};
    const targetDayOfWeek = dayMap[dayStr];
    
    if (targetDayOfWeek === undefined) return null;
    
    // 今日から7日以内で最初の該当曜日を探す
    for (let i = 0; i <= 7; i++) {
      const checkDate = new Date(today);
      checkDate.setDate(today.getDate() + i);
      if (checkDate.getDay() === targetDayOfWeek) {
        return checkDate;
      }
    }
  }
  
  // 既存の月次パターンの処理
  if (pattern.startsWith('monthly:第')) {
    const match = pattern.match(/第(\d+)([月火水木金土日])/);
    if (match) {
      const weekOfMonth = parseInt(match[1], 10);
      const dayOfWeekStr = match[2];
      const dayMap = {'日':0, '月':1, '火':2, '水':3, '木':4, '金':5, '土':6};
      const targetDayOfWeek = dayMap[dayOfWeekStr];

      if (targetDayOfWeek === undefined) return null;

      for (let i = 0; i < 2; i++) {
        let searchMonth = new Date(today.getFullYear(), today.getMonth() + i, 1);
        let firstDayOfMonth = new Date(searchMonth.getFullYear(), searchMonth.getMonth(), 1);
        let dayOfWeekOfFirst = firstDayOfMonth.getDay();
        
        let firstTargetDayOfMonth = 1 + (targetDayOfWeek - dayOfWeekOfFirst + 7) % 7;
        let targetDateNum = firstTargetDayOfMonth + (weekOfMonth - 1) * 7;
        
        let targetDate = new Date(searchMonth.getFullYear(), searchMonth.getMonth(), targetDateNum);

        if (targetDate.getMonth() === searchMonth.getMonth() && targetDate >= today) {
          return targetDate;
        }
      }
    }
  }
  
  // 毎日パターンの処理を追加
  if (pattern === 'daily') {
    return today;
  }
  
  return null;
}

/**
 * Slackイベントの重複実行を防止します。
 */
function shouldProcessEvent(requestBody) {
  const eventId = requestBody.event_id;
  const event = requestBody.event;
  
  if (!eventId || !event) return false;
  
  // メッセージのタイムスタンプとテキストを組み合わせて一意性を確保
  const messageSignature = event.ts ? `${eventId}_${event.ts}_${event.text}` : eventId;
  
  const scriptProperties = PropertiesService.getScriptProperties();
  const processedEvents = JSON.parse(scriptProperties.getProperty(PROCESSED_EVENTS_KEY) || '[]');

  const now = Date.now();
  // 10分以内の処理済みイベントをフィルタ
  const recentEvents = processedEvents.filter(e => now - e.timestamp < 10 * 60 * 1000);

  if (recentEvents.some(e => e.signature === messageSignature)) {
    console.log(`メッセージ ${messageSignature} は既に処理済みです`);
    return false;
  }

  recentEvents.push({ 
    id: eventId,
    signature: messageSignature,
    timestamp: now 
  });
  
  // 保存するデータ量を制限（最新100件まで）
  const eventsToSave = recentEvents.slice(-100);
  scriptProperties.setProperty(PROCESSED_EVENTS_KEY, JSON.stringify(eventsToSave));
  
  return true;
}

/**
 * ヘルプリクエストかどうかを判定します。
 */
function isHelpRequest(text) {
  if (!text) return false;
  return /ヘルプ|help|使い方|how to|教えて/i.test(text);
}

/**
 * 予定に関する情報（日付や時間）が含まれているかを判定します。
 */
function containsScheduleInfo(text) {
  if (!text) return false;
  const timePatterns = ['\\d{1,2}時', '\\d{1,2}:\\d{2}', '午前', '午後'];
  const datePatterns = ['今日', '明日', '明後日', '来週', '来月', '月曜', '火曜', '水曜', '木曜', '金曜', '土曜', '日曜', '\\d+月\\d+日', '\\d+/\\d+'];
  const hasTime = timePatterns.some(p => new RegExp(p).test(text));
  const hasDate = datePatterns.some(p => new RegExp(p).test(text));
  return hasTime || hasDate;
}

/**
 * チャンネル内で明示的に予定追加をリクエストしているかを判定します。
 */
function isScheduleRequest(text) {
  if (!text) return false;
  const keywords = ['予定.*追加', 'カレンダー.*追加', 'スケジュール.*登録'];
  return keywords.some(k => new RegExp(k, 'i').test(text));
}