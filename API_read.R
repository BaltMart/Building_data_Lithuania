library(httr)
library(jsonlite)
library(dplyr)

setwd("C:/Users/mbaltramaitis/OneDrive - Lietuvos bankas/Documents/Building analysis project")

# Define base API URL
base_url <- "https://maps.planuojustatau.lt/map-services/rest/services/sld/SLD/MapServer/2/query"

# Fetch all available IDs first
ids_url <- paste0(base_url, "?f=json&returnIdsOnly=true&where=1=1")
response_ids <- GET(ids_url)
data_ids <- fromJSON(content(response_ids, "text"))

# Extract object IDs
object_ids <- data_ids$objectIds
cat("Total objects to fetch:", length(object_ids), "\n")

# Batch requests based on maxRecordCount
records_per_request <- 100  # Maximum allowed by API
all_features <- list()  # Changed name for clarity

# Split object IDs into batches
id_batches <- split(object_ids, ceiling(seq_along(object_ids) / records_per_request))
cat("Number of batches:", length(id_batches), "\n")

for (i in seq_along(id_batches)) {
  batch <- id_batches[[i]]
  id_string <- paste(batch, collapse = ",")
  
  query_url <- paste0(base_url, "?f=json&where=OBJECTID%20IN%20(", id_string, ")&outFields=*&spatialRel=esriSpatialRelIntersects")
  
  cat("Fetching batch", i, "of", length(id_batches), "- IDs:", length(batch), "\n")
  
  response <- GET(query_url)
  
  # Check if request was successful
  if (status_code(response) != 200) {
    cat("Error in batch", i, "- Status:", status_code(response), "\n")
    next
  }
  
  data <- fromJSON(content(response, "text"))
  
  # Check if features exist and extract both attributes and geometry
  if (!is.null(data$features) && nrow(data$features) > 0) {
    # Extract attributes data frame
    batch_attributes <- data$features$attributes
    
    # Extract geometry coordinates
    batch_geometry <- data$features$geometry
    
    # Combine attributes with geometry coordinates
    batch_data <- cbind(batch_attributes, 
                        x = batch_geometry$x, 
                        y = batch_geometry$y)
    
    cat("Added", nrow(batch_data), "features from batch", i, "\n")
    
    # Add this batch's data to our collection
    all_features[[length(all_features) + 1]] <- batch_data
    
  } else {
    cat("No features returned for batch", i, "\n")
    if (!is.null(data$error)) {
      cat("API Error:", data$error$message, "\n")
    }
  }
  
  # Optional: Add a small delay to be respectful to the API
  Sys.sleep(0.1)
}

cat("Total features collected:", length(all_features), "\n")

# Convert results to a DataFrame
if (length(all_features) > 0) {
  # Since each element in all_features is already a data frame, use bind_rows directly
  df <- bind_rows(all_features)
  
  # Check for duplicates
  cat("Rows in final dataset:", nrow(df), "\n")
  if ("OBJECTID" %in% names(df)) {
    unique_ids <- length(unique(df$OBJECTID))
    cat("Unique OBJECTID values:", unique_ids, "\n")
    if (unique_ids < nrow(df)) {
      cat("Warning: Duplicates detected!\n")
      # Remove duplicates based on OBJECTID
      df <- df[!duplicated(df$OBJECTID), ]
      cat("After removing duplicates:", nrow(df), "rows\n")
    }
  }
} else {
  cat("No data collected\n")
  df <- data.frame()
}

# View the final dataset structure
print(paste("Final dataset dimensions:", nrow(df), "x", ncol(df)))
print("Column names:")
print(names(df))
print("First few rows:")
print(head(df[, c("OBJECTID", "STATINIOPILNASADRESAS", "x", "y")]))  # Show key columns including coordinates

#Saving the df as a relevant csv file
write.csv(df, "Build_intermediate.csv")
  