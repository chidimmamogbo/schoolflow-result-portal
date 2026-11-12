// Buttons (design system "Buttons"): one filled primary per view; 44px touch targets.
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { Slot } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-60 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-on-primary hover:opacity-90",
        secondary:
          "border border-border-strong bg-surface text-text hover:bg-surface-2",
        ghost: "text-text hover:bg-surface-2",
        danger: "bg-danger text-white hover:opacity-90",
        link: "min-h-0 px-0 text-primary underline-offset-4 hover:underline",
      },
      size: { md: "", sm: "min-h-9 px-3", icon: "size-11 px-0" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

type ButtonProps = ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean; busy?: boolean };

export function Button({
  className,
  variant,
  size,
  asChild,
  busy,
  children,
  disabled,
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot.Root : "button";
  return (
    <Component
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          {busy ? (
            <Loader2 className="animate-spin" aria-hidden="true" />
          ) : null}
          {children}
        </>
      )}
    </Component>
  );
}
