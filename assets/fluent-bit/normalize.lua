local function copy_if_missing(record, canonical, legacy)
    if record[canonical] == nil and record[legacy] ~= nil then
        record[canonical] = record[legacy]
    end
end

function normalize_mayajal_event(tag, timestamp, record)
    copy_if_missing(record, "session_id", "mayajal_session_id")
    copy_if_missing(record, "lab_id", "mayajal_lab_id")
    copy_if_missing(record, "user_id", "mayajal_user_id")
    copy_if_missing(record, "project_id", "mayajal_project_id")
    copy_if_missing(record, "service", "mayajal_service")

    if record["telemetry_source"] == nil then
        record["telemetry_source"] = "container"
    end
    if record["stream"] == nil and
       (record["source"] == "stdout" or record["source"] == "stderr") then
        record["stream"] = record["source"]
    end

    return 1, timestamp, record
end
