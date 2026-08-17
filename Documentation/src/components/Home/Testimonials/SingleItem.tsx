import React from "react";
import { ROUTES } from "@/constants/links";
import { Testimonial } from "@/types/testimonial";
import StarRating from "@/components/Common/StarRating";
import Image from "next/image";

const SingleItem = ({ testimonial }: { testimonial: Testimonial }) => {
  return (
    <div className="shadow-testimonial bg-white rounded-[10px] py-7.5 px-4 sm:px-8.5 m-1">
      <div className="mb-5">
        <StarRating rating={testimonial.rating} size={15} />
      </div>

      <p className="text-dark mb-6">{testimonial.review}</p>

      <a href={ROUTES.contact} className="flex items-center gap-4">
        <div className="w-12.5 h-12.5 rounded-full overflow-hidden">
          <Image
            src={testimonial.authorImg}
            alt="author"
            className="w-12.5 h-12.5 rounded-full overflow-hidden"
            width={50}
            height={50}
          />
        </div>

        <div>
          <h3 className="font-medium text-dark">{testimonial.authorName}</h3>
          <p className="text-custom-sm">{testimonial.authorRole}</p>
        </div>
      </a>
    </div>
  );
};

export default SingleItem;
