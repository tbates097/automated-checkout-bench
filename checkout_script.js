// At the top of the file, add shared constants
const TEMPLATE_FILE_NAME = "CO Template"; // Template file now in your 'My Drive'
const CHECKOUT_DRIVE_ID = "0AO6SeLt0pgQ8Uk9PVA"; // The destination Shared Drive

/**
 * Logs a message to the console for debugging.
 * @param {string} message The message to log.
 */
function logMessage(message) {
  console.log(message);
}

/**
 * Duplicates a template sheet from 'My Drive', renames it, and places it in the checkout drive.
 * @param {string} jobName The name for the new sheet, which is used as the filename.
 * @returns {string} A JSON string with the result, including the new file's ID and URL.
 */
function duplicateSheet(jobName) {
  try {
    // Get the destination folder (the root of the checkout drive)
    const checkoutFolder = DriveApp.getFolderById(CHECKOUT_DRIVE_ID);
    logMessage(`Destination folder is: '${checkoutFolder.getName()}'`);

    // Check if a file with the same name already exists in the destination
    const existingFiles = checkoutFolder.getFilesByName(jobName);
    if (existingFiles.hasNext()) {
      const existingFile = existingFiles.next();
      logMessage(`File '${jobName}' already exists. No new sheet will be created.`);
      return ContentService.createTextOutput(
        JSON.stringify({
          message: "A sheet with this job name already exists.",
          status: "exists",
          sheetId: existingFile.getId(),
          link: existingFile.getUrl()
        })
      ).setMimeType(ContentService.MimeType.JSON);
    }

    // Search for the template file directly in "My Drive"
    logMessage(`Searching for template file '${TEMPLATE_FILE_NAME}' in your 'My Drive'...`);
    const templateFiles = DriveApp.getFilesByName(TEMPLATE_FILE_NAME);
    if (!templateFiles.hasNext()) {
      throw new Error(`Template file not found in your 'My Drive': '${TEMPLATE_FILE_NAME}'`);
    }
    const templateFile = templateFiles.next();
    logMessage(`Template file found: '${templateFile.getName()}'`);

    // Create a copy of the template directly in the destination folder.
    // This is more reliable now that the source is 'My Drive'.
    const newFile = templateFile.makeCopy(jobName, checkoutFolder);

    // Open the new spreadsheet by its ID and rename the first sheet
    const newSpreadsheet = SpreadsheetApp.openById(newFile.getId());
    const sheet = newSpreadsheet.getSheets()[0];
    sheet.setName(jobName);

    logMessage(`Successfully created file '${jobName}' with ID: ${newFile.getId()}`);
    return ContentService.createTextOutput(
      JSON.stringify({
        message: "Sheet duplicated and placed in destination successfully.",
        status: "success",
        sheetId: newFile.getId(),
        link: newSpreadsheet.getUrl()
      })
    ).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    logMessage(`Error in duplicateSheet: ${error.toString()} \nStack: ${error.stack}`);
    return ContentService.createTextOutput(
      JSON.stringify({
        status: "error",
        message: `Error duplicating sheet: ${error.toString()}`
      })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Populates a specified sheet with data from a payload.
 * @param {string} jobName The name of the target spreadsheet file.
 * @param {Object} cellData A dictionary where keys match labels in column A.
 * @returns {string} A JSON string with the result of the operation.
 */
function populateSheet(jobName, cellData) {
  try {
    // The new sheet is in the root of the CHECKOUT_DRIVE_ID
    const checkoutFolder = DriveApp.getFolderById(CHECKOUT_DRIVE_ID);
    const files = checkoutFolder.getFilesByName(jobName);

    if (files.hasNext()) {
      const file = files.next();
      const spreadsheet = SpreadsheetApp.open(file);
      // The sheet/tab name is assumed to be the same as the jobName/filename
      const sheet = spreadsheet.getSheetByName(jobName);

      if (!sheet) {
        throw new Error(`Sheet tab '${jobName}' not found in spreadsheet '${file.getName()}'.`);
      }

      logMessage(`Populating sheet for job: '${jobName}'`);
      // Read all of column A values once for efficiency
      const rangeA = sheet.getRange("A1:A" + sheet.getLastRow());
      const valuesA = rangeA.getValues();

      // Create a map for faster lookups of row index by key
      const keyIndexMap = new Map();
      valuesA.forEach((row, index) => {
        if (row[0]) { // Ensure the cell is not empty
          keyIndexMap.set(row[0].toString(), index + 1); // Store 1-based index
        }
      });

      // Process all fields in cellData
      for (const key in cellData) {
        if (keyIndexMap.has(key)) {
          const rowIndex = keyIndexMap.get(key);
          const value = cellData[key];
          sheet.getRange(rowIndex, 2).setValue(value); // Set value in column B
        } else {
          logMessage(`Key '${key}' from payload not found in column A.`);
        }
      }

      return ContentService.createTextOutput(
        JSON.stringify({
          status: "success",
          message: "Sheet populated successfully",
          sheetId: file.getId(),
          link: file.getUrl()
        })
      ).setMimeType(ContentService.MimeType.JSON);
    } else {
      throw new Error(`File '${jobName}' not found in the checkout drive.`);
    }
  } catch (error) {
    logMessage(`Error in populateSheet: ${error.message}`);
    return ContentService.createTextOutput(
      JSON.stringify({
        status: "error",
        message: `Error populating sheet: ${error.message}`
      })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}

function doPost(e) {
  let requestData;
  
  // Parse JSON payload
  try {
      requestData = JSON.parse(e.postData.contents);
  } catch (error) {
      return ContentService.createTextOutput("Error parsing request data: " + error.message);
  }

  const requiredToken = "r~unPA2+x*Y-tHmKY>-D";

  // Validate token
  if (requestData.token !== requiredToken) {
      return ContentService.createTextOutput("Unauthorized request.");
  }

  const jobName = requestData.jobName;
  const action = requestData.action;

  const stageType = requestData.stageType || null;

  if (action === "create") {
  const result = duplicateSheet(jobName);
  return result;  // Just return the result directly!;

} else if (action === "populate") {
  // You said you are sending a dictionary as JSON-encoded string
  let cellData = requestData.cellData;
  // parse it if it's still a string
  if (typeof cellData === "string") {
    try {
      cellData = JSON.parse(cellData);
    } catch (err) {
      return ContentService
        .createTextOutput("Error parsing cellData: " + err.message)
        .setMimeType(ContentService.MimeType.TEXT);
    }
  }

  // Now cellData is an object (dictionary)
  const result = populateSheet(jobName, cellData);
  return result;

} else {
  return ContentService
    .createTextOutput("Invalid action specified.")
    .setMimeType(ContentService.MimeType.TEXT);
}
}

function doGet(e) {
return ContentService.createTextOutput("Web app is reachable. Use POST requests for actions.");
}

function testScript() {
    // Test data to simulate Python requests
    const testData = {
        create: {
            token: "r~unPA2+x*Y-tHmKY>-D",
            jobName: "100002-TEST",
            action: "create"
        },
        populate: {
            token: "r~unPA2+x*Y-tHmKY>-D",
            jobName: "100002-TEST",
            action: "populate",
            cellData: JSON.stringify({
                "Testing Technician": "Test User",
                "Date of Testing": new Date().toISOString(),
                "Axis: 1": {
                    "Halls": "Passed",
                    "Marker": "Passed",
                    "Limits": "Passed",
                    "Total Travel": "26.4"
                },
                "Axis: 2": {
                    "Halls": "Failed",
                    "Marker": "Passed",
                    "Limits": "Passed",
                    "Total Travel": "26.2"
                }
            })
        }
    };

    // Simulate create request
    console.log("Testing create sheet...");
    const createResult = doPost({
        postData: {
            contents: JSON.stringify(testData.create)
        }
    });
    console.log("Create result:", createResult.getContent());

    // Increase wait time for file creation and indexing
    console.log("Waiting for file to be fully created and indexed...");
    Utilities.sleep(5000);  // Increased to 5 seconds

    // Verify file exists before populating
    const folder = DriveApp.getFolderById(SHARED_DRIVE_ID)
                         .getFoldersByName(HEXAPOD_FOLDER_NAME).next();
    const files = folder.getFilesByName(testData.create.jobName);
    
    if (files.hasNext()) {
        console.log("File found, proceeding with populate...");
        // Simulate populate request
        const populateResult = doPost({
            postData: {
                contents: JSON.stringify(testData.populate)
            }
        });
        console.log("Populate result:", populateResult.getContent());
    } else {
        console.log("Error: File not found after creation. Drive indexing may be delayed.");
    }
}

// Add cleanup function for test files
function cleanupTestFiles() {
    const folder = DriveApp.getFolderById(SHARED_DRIVE_ID)
                         .getFoldersByName(HEXAPOD_FOLDER_NAME).next();
    const files = folder.getFilesByName("100000-TEST");
    
    while (files.hasNext()) {
        const file = files.next();
        console.log("Deleting test file:", file.getName());
        file.setTrashed(true);
    }
}


