"use client";

// The signed-in frame (design "Layout"): a sidebar that collapses to icons with
// tooltips and remembers the choice, a slide-out drawer on phones, and a header
// with the notice bell, theme toggle and profile menu.
import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  ChevronsLeft,
  ChevronsRight,
  LogOut,
  Menu,
  Monitor,
  Moon,
  Sun,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { Dialog, DropdownMenu, Tooltip } from "radix-ui";
import { type ReactNode, useState } from "react";

import { type NavItem, menuFor, roleLabel } from "@/components/shell/nav";
import { Button } from "@/components/ui/button";
import { api, ok } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";
import { featureOn, roleOf, useLogout } from "@/lib/auth";
import { cn } from "@/lib/utils";

const COLLAPSED_KEY = "sf-sidebar-collapsed";

function useCollapsed(): [boolean, (next: boolean) => void] {
  // Remembered per browser (design rule). The shell renders only in the browser
  // (after the signed-in check), so storage can be read straight away.
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(COLLAPSED_KEY) === "1";
    } catch {
      return false; // Storage can be blocked; the sidebar then starts expanded.
    }
  });
  const set = (next: boolean) => {
    setCollapsed(next);
    try {
      window.localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
    } catch {
      // Not remembered, but still works.
    }
  };
  return [collapsed, set];
}

function isActive(path: string, href: string): boolean {
  return (
    path === href || (href.split("/").length > 2 && path.startsWith(`${href}/`))
  );
}

function NavLinks({
  items,
  collapsed,
  onNavigate,
}: {
  items: NavItem[];
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const path = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {items.map((item, index) => {
        const heading =
          item.group && item.group !== items[index - 1]?.group && !collapsed
            ? item.group
            : null;
        const active = isActive(path, item.href);
        const Icon = item.icon;
        const link = (
          <Link
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex min-h-11 items-center gap-3 rounded-md px-3 text-sm font-medium text-text hover:bg-surface-2",
              active && "bg-primary-soft text-primary",
              collapsed && "justify-center px-0",
            )}
          >
            <Icon className="size-5 shrink-0" aria-hidden="true" />
            <span className={cn(collapsed && "sr-only")}>{item.label}</span>
          </Link>
        );
        return (
          <div key={item.href}>
            {heading ? (
              <p className="mt-4 mb-1 px-3 text-xs font-medium tracking-wide text-muted">
                {heading}
              </p>
            ) : null}
            {collapsed ? (
              <Tooltip.Root>
                <Tooltip.Trigger asChild>{link}</Tooltip.Trigger>
                <Tooltip.Portal>
                  <Tooltip.Content
                    side="right"
                    className="z-50 rounded-md bg-text px-2 py-1 text-sm text-bg"
                  >
                    {item.label}
                  </Tooltip.Content>
                </Tooltip.Portal>
              </Tooltip.Root>
            ) : (
              link
            )}
          </div>
        );
      })}
    </nav>
  );
}

function Brand({ me, collapsed }: { me: Me; collapsed: boolean }) {
  const name = me.school?.name ?? "SchoolFlow Result Portal";
  const initials = me.school?.code ?? "SF";
  return (
    <div className="flex items-center gap-3 px-1 py-2">
      <span
        aria-hidden="true"
        className="flex size-10 shrink-0 items-center justify-center rounded-md text-xs font-bold text-white"
        style={{ background: me.school?.colour ?? "var(--primary)" }}
      >
        {initials}
      </span>
      {collapsed ? (
        <span className="sr-only">{name}</span>
      ) : (
        <span className="leading-5 font-bold">{name}</span>
      )}
    </div>
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const options = [
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
    { value: "system", label: "System", icon: Monitor },
  ];
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button variant="ghost" size="icon" aria-label="Theme">
          <Sun className="dark:hidden" aria-hidden="true" />
          <Moon className="hidden dark:block" aria-hidden="true" />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          className="z-50 min-w-36 rounded-md border border-border bg-surface p-1 shadow-md"
        >
          <DropdownMenu.RadioGroup value={theme} onValueChange={setTheme}>
            {options.map(({ value, label, icon: Icon }) => (
              <DropdownMenu.RadioItem
                key={value}
                value={value}
                className="flex min-h-11 cursor-pointer items-center gap-2 rounded px-2 text-sm outline-none data-[highlighted]:bg-surface-2 data-[state=checked]:font-semibold"
              >
                <Icon className="size-4" aria-hidden="true" />
                {label}
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function NoticeBell({ me }: { me: Me }) {
  const on = roleOf(me) === "super_admin" || featureOn(me, "notice_board");
  // The unread count refreshes every 60 seconds (D-086).
  const { data } = useQuery({
    queryKey: ["notices", "unread"],
    queryFn: () => ok(api.GET("/api/v1/notices/unread-count")),
    refetchInterval: 60_000,
    enabled: on,
    initialData: { unread: me.unread_notices },
  });
  if (!on) return null;
  const unread = data?.unread ?? 0;
  return (
    <Button asChild variant="ghost" size="icon" className="relative">
      <Link
        href="/notices"
        aria-label={unread ? `Notices, ${unread} unread` : "Notices"}
      >
        <Bell aria-hidden="true" />
        {unread ? (
          <span className="absolute top-1 right-1 min-w-5 rounded-full bg-danger px-1 text-xs font-bold text-white">
            {unread}
          </span>
        ) : null}
      </Link>
    </Button>
  );
}

function ProfileMenu({ me }: { me: Me }) {
  const logout = useLogout();
  const router = useRouter();
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button
          variant="ghost"
          aria-label="Profile menu"
          className="gap-2 px-2"
        >
          <span
            aria-hidden="true"
            className="flex size-8 items-center justify-center rounded-full bg-primary-soft text-xs font-bold text-primary"
          >
            {me.user.full_name
              .split(" ")
              .map((part) => part[0])
              .slice(0, 2)
              .join("")}
          </span>
          <span className="hidden flex-col items-start leading-tight md:flex">
            <span className="text-sm">{me.user.full_name}</span>
            <span className="text-xs text-muted">{roleLabel(me)}</span>
          </span>
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          className="z-50 min-w-48 rounded-md border border-border bg-surface p-1 shadow-md"
        >
          <DropdownMenu.Label className="px-2 py-1 text-sm">
            <span className="block font-semibold">{me.user.full_name}</span>
            <span className="block text-muted">{roleLabel(me)}</span>
          </DropdownMenu.Label>
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Item
            asChild
            className="flex min-h-11 items-center rounded px-2 text-sm outline-none data-[highlighted]:bg-surface-2"
          >
            <Link href="/change-password">Change password</Link>
          </DropdownMenu.Item>
          <DropdownMenu.Item
            className="flex min-h-11 cursor-pointer items-center gap-2 rounded px-2 text-sm outline-none data-[highlighted]:bg-surface-2"
            onSelect={async () => {
              await logout();
              router.replace("/login");
            }}
          >
            <LogOut className="size-4" aria-hidden="true" />
            Log out
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function AppShell({ me, children }: { me: Me; children: ReactNode }) {
  const items = menuFor(me);
  const [collapsed, setCollapsed] = useCollapsed();
  const [drawer, setDrawer] = useState(false);
  return (
    <Tooltip.Provider delayDuration={200}>
      <div className="flex min-h-screen">
        <aside
          className={cn(
            "sticky top-0 hidden h-screen shrink-0 flex-col gap-2 overflow-y-auto border-r border-border bg-surface p-3 transition-[width] duration-200 lg:flex",
            collapsed
              ? "w-[var(--sidebar-collapsed)]"
              : "w-[var(--sidebar-expanded)]",
          )}
        >
          <Brand me={me} collapsed={collapsed} />
          <NavLinks items={items} collapsed={collapsed} />
          <div className="mt-auto flex flex-col gap-2">
            <Button
              variant="ghost"
              size={collapsed ? "icon" : "md"}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!collapsed}
              onClick={() => setCollapsed(!collapsed)}
            >
              {collapsed ? (
                <ChevronsRight aria-hidden="true" />
              ) : (
                <ChevronsLeft aria-hidden="true" />
              )}
            </Button>
            {collapsed ? null : (
              <p className="px-3 text-xs text-muted">Powered by SchoolFlow</p>
            )}
          </div>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-16 items-center gap-2 border-b border-border bg-surface px-4">
            <Dialog.Root open={drawer} onOpenChange={setDrawer}>
              <Dialog.Trigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Open menu"
                  className="lg:hidden"
                >
                  <Menu aria-hidden="true" />
                </Button>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 lg:hidden" />
                <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col gap-2 overflow-y-auto bg-surface p-3 shadow-lg lg:hidden">
                  <Dialog.Title className="sr-only">Menu</Dialog.Title>
                  <Dialog.Description className="sr-only">
                    Main navigation
                  </Dialog.Description>
                  <div className="flex items-center justify-between">
                    <Brand me={me} collapsed={false} />
                    <Dialog.Close asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Close menu"
                      >
                        <X aria-hidden="true" />
                      </Button>
                    </Dialog.Close>
                  </div>
                  <NavLinks
                    items={items}
                    collapsed={false}
                    onNavigate={() => setDrawer(false)}
                  />
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
            <span className="truncate font-semibold lg:hidden">
              {me.school?.name ?? "SchoolFlow"}
            </span>
            <div className="ml-auto flex items-center gap-1">
              <NoticeBell me={me} />
              <ThemeToggle />
              <ProfileMenu me={me} />
            </div>
          </header>
          <main
            id="main"
            className="mx-auto w-full max-w-7xl flex-1 p-4 md:p-6"
          >
            {children}
          </main>
        </div>
      </div>
    </Tooltip.Provider>
  );
}
