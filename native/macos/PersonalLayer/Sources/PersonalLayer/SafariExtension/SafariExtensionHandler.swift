import SafariServices

class SafariExtensionHandler: SFSafariExtensionHandler {
    override func messageReceived(withName messageName: String, from page: SFSafariPage, userInfo: [String : Any]?) {
        if messageName == "CL_GET_BUNDLE" {
            do {
                let bundle = try GRDBDatabase.shared.loadSharedBundle()
                page.dispatchMessageToScript(withName: "CL_BUNDLE_RESPONSE", userInfo: ["bundle": bundle])
            } catch {
                page.dispatchMessageToScript(withName: "CL_BUNDLE_ERROR", userInfo: ["error": error.localizedDescription])
            }
        } else if messageName == "CL_TRACK" {
            guard let type = userInfo?["event_type"] as? String,
                  let payload = userInfo?["payload"] as? [String: Any] else { return }
            try? GRDBDatabase.shared.insertRawEvent(type: type, payload: payload)
            page.dispatchMessageToScript(withName: "CL_TRACK_OK", userInfo: [:])
        }
    }
}
