// OCR every PNG in a folder with Apple Vision; print JSON lines for text that contains an email address.
// Usage: swift ocr_emails.swift <folder>
// Output: {"file": name, "text": str, "x": left, "y": top, "w": width, "h": height} in pixel coordinates (top-left origin).
import Foundation
import Vision
import AppKit

let folder = URL(fileURLWithPath: CommandLine.arguments[1])
let files = try FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)
    .filter { $0.pathExtension == "png" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
let email = try NSRegularExpression(pattern: "[A-Za-z0-9._%+-]+ ?@ ?[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")

for f in files {
    guard let img = NSImage(contentsOf: f), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let W = Double(cg.width), H = Double(cg.height)
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: cg).perform([req])
    for obs in req.results ?? [] {
        guard let cand = obs.topCandidates(1).first else { continue }
        let s = cand.string
        let ns = s as NSString
        for m in email.matches(in: s, range: NSRange(location: 0, length: ns.length)) {
            guard let r = Range(m.range, in: s), let box = try? cand.boundingBox(for: r) else { continue }
            let bb = box.boundingBox
            let rec: [String: Any] = ["file": f.lastPathComponent, "text": ns.substring(with: m.range),
                                      "x": Int(bb.minX * W), "y": Int((1 - bb.maxY) * H), "w": Int(bb.width * W), "h": Int(bb.height * H)]
            let d = try JSONSerialization.data(withJSONObject: rec)
            print(String(data: d, encoding: .utf8)!)
        }
    }
}
