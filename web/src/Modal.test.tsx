import { render, fireEvent, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useState } from "react";
import Modal from "./Modal";
afterEach(cleanup);
function Test() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Open modal</button>
      {open && (
        <Modal labelledBy="title" onClose={() => setOpen(false)}>
          <h2 id="title">Test dialog</h2>
          <input data-autofocus aria-label="Name" />
          <button>Last button</button>
        </Modal>
      )}
    </>
  );
}
describe("modal accessibility", () => {
  it("traps keyboard focus, closes with Escape and restores the opener", () => {
    render(<Test />);
    const opener = screen.getByText("Open modal");
    opener.focus();
    fireEvent.click(opener);
    expect(screen.getByRole("textbox")).toHaveFocus();
    expect(opener.closest("[inert]")).not.toBeNull();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(screen.getByText("Last button")).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(screen.getByRole("textbox")).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
    expect(opener.closest("[inert]")).toBeNull();
  });
});
